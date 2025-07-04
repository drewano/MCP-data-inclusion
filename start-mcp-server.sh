#!/bin/bash
# Script pour lancer le MCP Server en mode debug

echo "🚀 Démarrage du MCP Server en mode debug..."
echo "📡 Port: 8000"
echo "🔧 Mode: développement local"
echo "==============================================="

# Charger les variables d'environnement locales
export $(cat .env| grep -v '#' | xargs)

# Naviguer vers le répertoire backend
unset MCP_API_PATH
cd backend

# Activer l'environnement virtuel si nécessaire
if [ -d "../.venv" ]; then
    source ../.venv/Scripts/activate
fi

# Lancer le serveur MCP avec logs détaillés
echo "🔥 Démarrage du serveur..."
python -m src.mcp.server

echo "❌ MCP Server arrêté" 