#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
project="gainmiles-startup-$(date +%s)-$$"
failure_project="${project}-failure"
temporary_dir=$(mktemp -d)
cleanup() {
    result=$?
    trap - EXIT
    if [ "$result" -ne 0 ]; then
        docker compose -p "$project" logs --no-color || true
        docker compose -p "$failure_project" logs --no-color || true
    fi
    docker compose -p "$project" down --volumes --remove-orphans >/dev/null 2>&1 || true
    docker compose -p "$failure_project" down --volumes --remove-orphans >/dev/null 2>&1 || true
    rm -f "$temporary_dir/failure.yaml" "$temporary_dir/failure.log"
    rmdir "$temporary_dir"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export API_PORT=0
docker compose -p "$project" up --build --wait --wait-timeout 90
docker compose -p "$project" exec -T api python -c \
    'import json; from urllib.request import urlopen; r = urlopen("http://127.0.0.1:8000/health", timeout=5); assert r.status == 200; assert json.load(r) == {"status": "ok"}'
echo "PASS: fresh containers migrate and serve healthy HTTP without seed"

migration_id=$(docker compose -p "$project" ps --all --quiet migrate)
test "$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$migration_id")" = "exited 0"
api_id=$(docker compose -p "$project" ps --quiet api)
test "$(docker inspect --format '{{.Image}}' "$migration_id")" = "$(docker inspect --format '{{.Image}}' "$api_id")"
docker compose -p "$project" run --rm migrate
echo "PASS: migration exits successfully, shares the API image, and can run again"

docker compose -p "$project" stop db
docker compose -p "$project" exec -T api python - <<'PY'
import json
from urllib.error import HTTPError
from urllib.request import urlopen

try:
    urlopen("http://127.0.0.1:8000/health", timeout=8)
except HTTPError as error:
    assert error.code == 503
    assert json.load(error) == {"status": "unavailable"}
else:
    raise AssertionError("Health must fail when PostgreSQL is stopped")
PY
docker compose -p "$project" up --wait --wait-timeout 90 db
docker compose -p "$project" exec -T api python -c \
    'from urllib.request import urlopen; assert urlopen("http://127.0.0.1:8000/health", timeout=5).status == 200'
echo "PASS: health reports a database outage and recovers without restarting the API"

cat > "$temporary_dir/failure.yaml" <<'YAML'
services:
  migrate:
    command: ["flask", "--app", "app", "db", "upgrade", "missing_startup_test_revision"]
YAML
if docker compose -p "$failure_project" -f compose.yaml -f "$temporary_dir/failure.yaml" \
    up --no-build --wait --wait-timeout 90 > "$temporary_dir/failure.log" 2>&1; then
    echo "FAIL: startup succeeded despite a migration failure" >&2
    exit 1
fi
migration_id=$(docker compose -p "$failure_project" ps --all --quiet migrate)
test -n "$migration_id"
test "$(docker inspect --format '{{.State.Status}}' "$migration_id")" = "exited"
test "$(docker inspect --format '{{.State.ExitCode}}' "$migration_id")" -ne 0
api_id=$(docker compose -p "$failure_project" ps --all --quiet api)
if [ -n "$api_id" ]; then
    test "$(docker inspect --format '{{.State.StartedAt}}' "$api_id")" = "0001-01-01T00:00:00Z"
fi
docker compose -p "$failure_project" logs --no-color migrate
echo "PASS: failed migration prevents initial API startup and leaves diagnostic logs"
