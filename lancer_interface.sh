#!/usr/bin/env bash

set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "L'application n'est pas installée. Lancez d'abord ./install_linux.sh"
    exit 1
fi

exec "$PYTHON" -m ping_table_ja.gui
