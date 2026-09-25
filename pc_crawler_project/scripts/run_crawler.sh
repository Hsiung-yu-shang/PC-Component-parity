#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON="$PROJECT_ROOT/../.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$PROJECT_ROOT/venv/bin/python"
fi
exec "$PYTHON" "$PROJECT_ROOT/forge_backend_server/manage.py" sync_products "$@"
