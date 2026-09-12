#!/bin/sh
# Optional arguments are forwarded as docker compose options (for example -p).
set -eu

cd "$(dirname "$0")/.."
docker compose "$@" stop api
docker compose "$@" build
docker compose "$@" run --rm migrate
docker compose "$@" up --no-deps --wait --wait-timeout 90 api
