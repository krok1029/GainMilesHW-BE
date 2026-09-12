#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
project="gainmiles-handoff-$(date +%s)-$$"
temporary_dir=$(mktemp -d)
cp .env.example "$temporary_dir/handoff.env"
export API_PORT=0
compose() {
    docker compose --env-file "$temporary_dir/handoff.env" -p "$project" "$@"
}
http_check() {
    compose exec -T api python - "$1" < tests/handoff_client.py
}
cleanup() {
    result=$?
    trap - EXIT
    if [ "$result" -ne 0 ]; then
        compose logs --no-color || true
        if [ -f "$temporary_dir/update-failure.log" ]; then
            cat "$temporary_dir/update-failure.log"
        fi
    fi
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    rm -f "$temporary_dir/handoff.env" "$temporary_dir/failure.yaml" \
        "$temporary_dir/update-failure.log"
    rmdir "$temporary_dir"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

compose up --build --wait --wait-timeout 90
http_check empty
migration_id=$(compose ps --all --quiet migrate)
test "$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$migration_id")" = "exited 0"
test "$(compose exec -T api flask --app app seed-demo)" = "Created: 4; skipped: 0."
http_check seeded
http_check crud

compose restart api
compose up --no-deps --wait --wait-timeout 90 api
http_check persisted
echo "PASS: normal restart preserves edits and does not seed"

old_api=$(compose ps --quiet api)
compose build api
compose up --no-deps --force-recreate --wait --wait-timeout 90 api
test "$(compose ps --quiet api)" != "$old_api"
http_check persisted
echo "PASS: rebuilt application container preserves DB volume and does not seed"

compose down
compose up --wait --wait-timeout 90
http_check persisted
test "$(compose exec -T api flask --app app seed-demo)" = "Created: 1; skipped: 3."
http_check reseeded
test "$(compose exec -T api flask --app app seed-demo)" = "Created: 0; skipped: 4."
http_check reseeded
echo "PASS: down preserves data; explicit seed restores only the deleted sample"

sh scripts/update-environment.sh --env-file "$temporary_dir/handoff.env" -p "$project"
http_check reseeded
before_revision=$(compose exec -T api flask --app app db current)
echo "PASS: existing environment update stops API, builds, migrates, then starts"

cat > "$temporary_dir/failure.yaml" <<'YAML'
services:
  migrate:
    command: ["flask", "--app", "app", "db", "upgrade", "missing_handoff_test_revision"]
YAML
if sh scripts/update-environment.sh --env-file "$temporary_dir/handoff.env" \
    -p "$project" -f compose.yaml -f "$temporary_dir/failure.yaml" \
    > "$temporary_dir/update-failure.log" 2>&1; then
    echo "FAIL: environment update succeeded despite migration failure" >&2
    exit 1
fi
api_id=$(compose ps --all --quiet api)
test -n "$api_id"
test "$(docker inspect --format '{{.State.Status}}' "$api_id")" = "exited"
grep -F 'missing_handoff_test_revision' "$temporary_dir/update-failure.log"
after_revision=$(compose run --rm --no-deps api flask --app app db current)
test "$before_revision" = "$after_revision"
echo "PASS: failed migration leaves existing API stopped, revision unchanged, diagnostics available"

sh scripts/update-environment.sh --env-file "$temporary_dir/handoff.env" -p "$project"
http_check reseeded
echo "PASS: explicit recovery preserves all existing data"

compose down --volumes
compose up --wait --wait-timeout 90
http_check empty
echo "PASS: explicit volume reset removes data and recreates schema without seed"
