#!/bin/sh

set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "L'application n'est pas installée. Lancez d'abord ./install_linux.sh"
    exit 1
fi

exec "$PYTHON" -m ping_table_ja.editeur_configuration "$@"
