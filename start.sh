#!/usr/bin/env bash
# ======================================================================
#            🚀  AGENTREADY - SCRIPT DE DÉMARRAGE (MAC / LINUX)
# ======================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "======================================================================"
echo "           🚀  AGENTREADY - COMMERCE AGENTIQUE & GEO"
echo "======================================================================"
echo ""
echo "Initialisation de l'environnement..."

# Détection de Python 3
if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
else
    echo "❌ [ERREUR] Python n'est pas installé ou n'est pas dans le PATH."
    echo "Installez Python 3.11+ ou utilisez Docker : docker compose up"
    exit 1
fi

# Gestion de l'environnement virtuel (.venv)
if [ ! -d ".venv" ]; then
    echo "📦 Création de l'environnement virtuel .venv..."
    $PY_CMD -m venv .venv
fi

# Activation de l'environnement virtuel
source .venv/bin/activate

# Installation / mise à jour des dépendances
echo "⚙️ [1/3] Vérification des dépendances requises..."
pip install -q -r requirements.txt

# Démarrage du serveur FastAPI
echo "🌐 [2/3] Démarrage du serveur AgentReady sur http://localhost:8000..."
echo "Pour arrêter le serveur, faites Ctrl + C"
echo ""

uvicorn server:app --host 0.0.0.0 --port 8000 --reload
