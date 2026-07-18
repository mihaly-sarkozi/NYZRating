#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup.dump>" >&2
  exit 1
fi

DUMP="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -z "${DATABASE_URL:-}" ]]; then
  if [[ -f "${ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${ROOT}/.env"
    set +a
  fi
fi

: "${DATABASE_URL:?DATABASE_URL is required}"
[[ -f "${DUMP}" ]] || { echo "Missing dump: ${DUMP}" >&2; exit 1; }

echo "Restoring ${DUMP} into ${DATABASE_URL}"
pg_restore --clean --if-exists --no-owner --no-privileges -d "${DATABASE_URL}" "${DUMP}"
echo "Restore complete"
