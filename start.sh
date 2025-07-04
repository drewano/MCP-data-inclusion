#!/bin/bash

# Script de lancement pour l'application DataInclusion avec interface Gradio
# Ce script configure et lance tous les services nécessaires

set -e  # Arrête le script en cas d'erreur

echo "========================================"
echo "🚀 Lancement de DataInclusion avec Gradio"
echo "========================================"

# Vérifier si Docker et docker-compose sont installés
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez installer Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose n'est pas installé. Veuillez installer docker-compose first."
    exit 1
fi

# Vérifier si le fichier .env existe
if [ ! -f .env ]; then
    echo "⚠️  Fichier .env manquant. Création depuis .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Fichier .env créé. Veuillez le configurer avec vos clés API."
        echo "📝 Éditez .env et ajoutez votre OPENAI_API_KEY et DATA_INCLUSION_API_KEY"
        echo ""
        echo "Une fois configuré, relancez: ./start.sh"
        exit 0
    else
        echo "❌ Fichier .env.example introuvable. Veuillez le créer."
        exit 1
    fi
fi

# Vérifier les variables critiques dans .env
echo "🔍 Vérification de la configuration..."
source .env

if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your-openai-key-here" ]; then
    echo "❌ OPENAI_API_KEY manquante dans .env"
    echo "💡 Ajoutez votre clé OpenAI dans le fichier .env"
    exit 1
fi

if [ -z "$DATA_INCLUSION_API_KEY" ] || [ "$DATA_INCLUSION_API_KEY" = "your-api-key-here" ]; then
    echo "❌ DATA_INCLUSION_API_KEY manquante dans .env"
    echo "💡 Ajoutez votre clé DataInclusion dans le fichier .env"
    exit 1
fi

echo "✅ Configuration validée"
echo ""

# Nettoyer les anciens conteneurs si demandé
if [ "$1" = "--clean" ]; then
    echo "🧹 Nettoyage des anciens conteneurs..."
    docker-compose down --volumes --remove-orphans
    docker system prune -f
    echo "✅ Nettoyage terminé"
    echo ""
fi

# Construire et lancer les services
echo "🔨 Construction des images Docker..."
docker-compose build

echo ""
echo "🚀 Démarrage des services..."
docker-compose up -d

echo ""
echo "⏳ Attente du démarrage complet des services..."

# Attendre que tous les services soient prêts
echo "📡 Vérification du serveur MCP..."
while ! docker-compose exec -T mcp_server curl -f http://localhost:8000/health > /dev/null 2>&1; do
    echo "   ⏳ MCP Server démarrage en cours..."
    sleep 5
done
echo "   ✅ MCP Server opérationnel"

echo "🤖 Vérification du serveur Agent..."
while ! docker-compose exec -T agent_server curl -f http://localhost:8001/.well-known/agent.json > /dev/null 2>&1; do
    echo "   ⏳ Agent Server démarrage en cours..."
    sleep 5
done
echo "   ✅ Agent Server opérationnel"

echo "🎨 Vérification de l'interface Gradio..."
while ! docker-compose exec -T gradio_interface curl -f http://localhost:7860 > /dev/null 2>&1; do
    echo "   ⏳ Interface Gradio démarrage en cours..."
    sleep 5
done
echo "   ✅ Interface Gradio opérationnelle"

echo ""
echo "========================================"
echo "🎉 Tous les services sont opérationnels !"
echo "========================================"
echo ""
echo "📱 Interfaces disponibles :"
echo "   🎨 Interface Gradio:     http://localhost:7860"
echo "   🤖 Agent API:           http://localhost:8001"
echo "   🛠️  MCP Server:          http://localhost:8000"
echo "   🗄️  Redis:               localhost:6379"
echo ""
echo "📊 Monitoring :"
echo "   📋 Logs en temps réel:   docker-compose logs -f"
echo "   📈 État des services:    docker-compose ps"
echo "   🔍 Logs spécifiques:"
echo "       - Gradio:           docker-compose logs -f gradio_interface"
echo "       - Agent:            docker-compose logs -f agent_server"
echo "       - MCP:              docker-compose logs -f mcp_server"
echo ""
echo "🛑 Pour arrêter :"
echo "   docker-compose down"
echo ""
echo "🔄 Pour redémarrer :"
echo "   docker-compose restart"
echo ""
echo "🧹 Pour nettoyer complètement :"
echo "   ./start.sh --clean"
echo ""
echo "✨ Interface Gradio prête à l'usage sur http://localhost:7860"
echo "========================================" 