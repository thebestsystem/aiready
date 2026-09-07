@echo off
chcp 65001 >nul
title AgentReady - Lanceur de Serveur MVP
color 0B

echo ======================================================================
echo              AGENTREADY - COMMERCE AGENTIQUE & GEO
echo ======================================================================
echo.
echo  Initialisation de l'environnement...
cd /d "%~dp0"

REM 1. Verification et initialisation du fichier .env
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creation automatique de .env depuis .env.example...
        copy ".env.example" ".env" >nul
    )
)

REM 2. Detection dynamique de Node.js
where node >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Node.js detecte dans le PATH systeme.
) else (
    if exist "C:\node-v24-LTS\node.exe" (
        set "PATH=C:\node-v24-LTS;%PATH%"
        echo [OK] Node.js detecte dans C:\node-v24-LTS (ajoute au PATH de session)
    )
)

REM 3. Detection universelle de Python
set "PY_CMD="

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    echo [OK] Environnement virtuel (.venv) detecte.
    goto python_found
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    echo [OK] Python detecte dans le PATH systeme.
    goto python_found
)

if exist "C:\python-3.13.15\python.exe" (
    set "PY_CMD=C:\python-3.13.15\python.exe"
    echo [OK] Python detecte dans C:\python-3.13.15.
    goto python_found
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py -3"
    echo [OK] Lanceur Windows py detecte.
    goto python_found
)

if "%PY_CMD%"=="" (
    echo.
    echo [ERREUR] Impossible de trouver Python sur cette machine.
    echo    - Installez Python 3.11+ depuis https://python.org (en cochant "Add to PATH")
    echo    - Ou lancez le projet avec Docker : docker compose up
    echo.
    pause
    exit /b 1
)

:python_found
REM 4. Verification et installation des dependances
echo [1/3] Verification des librairies requises (FastAPI, ReportLab, GenAI)...
%PY_CMD% -m pip install -q -r requirements.txt >nul 2>&1
if %errorlevel% neq 0 (
    echo [ATTENTION] Installation silencieuse en cours d'ajustement...
    %PY_CMD% -m pip install -r requirements.txt
)

REM 5. Lancement des serveurs
echo [2/3] Demarrage du serveur AgentReady sur le port 8000...
start "AgentReady Server (Port 8000)" cmd /k "%PY_CMD% -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"

start "AgentReady Frontend Backup (Port 3000)" /min cmd /k "%PY_CMD% -m http.server 3000"

timeout /t 2 /nobreak >nul

REM 6. Ouverture automatique du navigateur
echo [3/3] Ouverture automatique de l'application dans votre navigateur...
start http://localhost:8000/

echo.
echo ======================================================================
echo    AGENTREADY EST EN LIGNE ET PRET !
echo.
echo    - Application principale : http://localhost:8000/
echo    - Port secondaire        : http://localhost:3000/
echo    - Fichier leads          : leads.csv
echo.
echo    Pour arreter les serveurs, fermez simplement les fenetres ouvertes.
echo ======================================================================
echo.
echo Vous pouvez minimiser cette fenetre.
pause
