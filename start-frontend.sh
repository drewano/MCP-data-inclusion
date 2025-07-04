#!/bin/bash
# Script pour lancer le Frontend Next.js en mode debug

echo "🌐 Démarrage du Frontend Next.js en mode debug..."
echo "📡 Port: 3000"
echo "🔧 Mode: développement local"
echo "🔗 Backend API: http://localhost:8001"
echo "==============================================="

# Naviguer vers le répertoire frontend
cd frontend

# Configurer les variables d'environnement pour Next.js
export NEXT_PUBLIC_API_URL=http://localhost:8001
export NODE_ENV=development

# Vérifier si node_modules existe
if [ ! -d "node_modules" ]; then
    echo "📦 Installation des dépendances..."
    npm install
fi

# Lancer Next.js en mode développement
echo "🔥 Démarrage du serveur de développement..."
npm run dev

echo "❌ Frontend arrêté" 