@echo off
setlocal

cd /d "%~dp0"
set "VENV_DIR=%CD%\.venv"

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 goto :python_missing
    set "PYTHON_CMD=python"
)

echo Creation de l'environnement virtuel dans "%VENV_DIR%"...
%PYTHON_CMD% -m venv "%VENV_DIR%"
if errorlevel 1 goto :failure

echo Mise a jour de pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failure

echo Installation de Double KO 32 et de ses dependances...
"%VENV_DIR%\Scripts\python.exe" -m pip install --editable "%CD%"
if errorlevel 1 goto :failure

echo.
echo Installation terminee.
echo Pour activer l'environnement : .venv\Scripts\activate.bat
echo Puis lancez l'interface avec lancer_interface.bat
goto :end

:python_missing
echo Erreur : Python 3 est introuvable.
echo Installez-le depuis https://www.python.org/downloads/windows/
echo Cochez l'option "Add Python to PATH" pendant l'installation.
goto :failure

:failure
echo.
echo L'installation a echoue.
exit /b 1

:end
endlocal
