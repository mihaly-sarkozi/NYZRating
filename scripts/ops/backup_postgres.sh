#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="${ROOT}/backend"
OUT_DIR="${1:-${ROOT}/backups/postgres}"
mkdir -p "${OUT_DIR}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  if [[ -f "${ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${ROOT}/.env"
    set +a
  fi
fi

: "${DATABASE_URL:?DATABASE_URL is required}"

STAMP="$(date +%Y%m%d_%H%M%S)"
TARGET="${OUT_DIR}/aiplaza_${STAMP}.dump"

echo "Backing up Postgres to ${TARGET}"
pg_dump "${DATABASE_URL}" -Fc -f "${TARGET}"
echo "Done: ${TARGET}"
