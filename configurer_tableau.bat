@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo L'application n'est pas installee.
    echo Lancez d'abord install_windows.bat
    pause
    exit /b 1
)

start "Configuration du tableau" ".venv\Scripts\pythonw.exe" -m ping_table_ja.editeur_configuration %*
endlocal
