@echo off
chcp 65001 >nul
title AgentReady - Lanceur de Serveur MVP
color 0B

echo ======================================================================
echo            🚀  AGENTREADY - COMMERCE AGENTIQUE & GEO
echo ======================================================================
echo.
echo  Initialisation de l'environnement...
cd /d "%~dp0"

:: Verification de Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Python n'est pas installe ou n'est pas dans votre PATH.
    echo Veuillez installer Python depuis https://python.org
    pause
    exit /b
)

:: Installation rapide des dependances requises au besoin
echo [1/3] Verification des librairies requises (FastAPI, ReportLab, GenAI)...
python -m pip install -q -r requirements.txt >nul 2>&1

:: Lancement du serveur unifie (API + Frontend integre)
echo [2/3] Demarrage du serveur AgentReady sur le port 8000...
start "AgentReady Server (Port 8000)" cmd /k "python -m uvicorn server:app --host 127.0.0.1 --port 8000"

:: Optionnel : serveur port 3000 pour compatibilite historique
start "AgentReady Frontend Backup (Port 3000)" /min cmd /k "python -m http.server 3000"

:: Temporisation pour laisser le serveur s'initialiser
timeout /t 2 /nobreak >nul

:: Ouverture automatique dans le navigateur par defaut
echo [3/3] Ouverture automatique de l'application dans votre navigateur...
start http://localhost:8000/

echo.
echo ======================================================================
echo  ✅  AGENTREADY EST EN LIGNE ET PRET POUR VOS DEMOS !
echo.
echo  - Application principale : http://localhost:8000/
echo  - Port secondaire        : http://localhost:3000/
echo  - Leads captures         : leads.csv
echo.
echo  Pour arreter les serveurs, fermez simplement les fenetres correspondantes.
echo ======================================================================
echo.
echo Vous pouvez maintenant minimiser cette fenetre.
pause
