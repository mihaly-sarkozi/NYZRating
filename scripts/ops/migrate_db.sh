#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="${ROOT}/backend"

cd "${BACKEND}"
echo "Running public + tenant schema migrations via init_db.py"
python3 scripts/init_db.py
echo "Migration complete"
