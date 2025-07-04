#!/bin/bash
# Script pour lancer l'Agent Server en mode debug

echo "🤖 Démarrage de l'Agent Server en mode debug..."
echo "📡 Port: 8001"
echo "🔧 Mode: développement local"
echo "🔗 MCP Server: http://localhost:8000/mcp"
echo "==============================================="

# Charger les variables d'environnement locales
export $(cat .env | grep -v '#' | xargs)

# Naviguer vers le répertoire backend
cd backend

# Activer l'environnement virtuel si nécessaire
if [ -d "../.venv" ]; then
    source ../.venv/Scripts/activate
fi

# Lancer l'agent server avec logs détaillés
echo "🔥 Démarrage du serveur..."
python main.py

echo "❌ Agent Server arrêté" 