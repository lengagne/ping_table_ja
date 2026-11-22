#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Erreur : Python 3 est introuvable."
    echo "Installez Python 3 et le module venv avec votre gestionnaire de paquets."
    echo "Exemple Ubuntu/Debian : sudo apt install python3 python3-venv"
    exit 1
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Erreur : le module graphique Tkinter est manquant."
    echo "Exemple Ubuntu/Debian : sudo apt install python3-tk"
    exit 1
fi

echo "Creation de l'environnement virtuel dans $VENV_DIR..."
python3 -m venv "$VENV_DIR"

echo "Mise a jour de pip..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip

echo "Installation de Double KO 32 et de ses dependances..."
"$VENV_DIR/bin/python" -m pip install --editable "$PROJECT_DIR"

echo
echo "Installation terminee."
echo "Pour activer l'environnement : source \"$VENV_DIR/bin/activate\""
echo "Puis lancez l'interface : ./lancer_interface.sh"
