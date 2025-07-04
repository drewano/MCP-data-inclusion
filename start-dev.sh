#!/bin/bash
# Script principal pour lancer l'application en mode debug

echo "🔧 MODE DEBUG - DÉVELOPPEMENT LOCAL"
echo "===================================="
echo ""
echo "📋 Instructions de démarrage :"
echo ""
echo "1️⃣  Redis est déjà lancé (Docker)"
echo "2️⃣  Ouvrez 3 terminaux différents :"
echo ""
echo "   Terminal 1 - MCP Server :"
echo "   ./start-mcp-server.sh"
echo ""
echo "   Terminal 2 - Agent Server :"
echo "   ./start-agent-server.sh"
echo ""
echo "   Terminal 3 - Frontend :"
echo "   ./start-frontend.sh"
echo ""
echo "🌐 Une fois tout lancé, accédez à :"
echo "   Frontend: http://localhost:3000"
echo "   Agent API: http://localhost:8001"
echo "   MCP API: http://localhost:8000"
echo ""
echo "🛠️  Pour arrêter Redis :"
echo "   docker stop redis-local && docker rm redis-local"
echo ""
echo "🔥 DÉMARRAGE AUTOMATIQUE (expérimental) :"
read -p "Voulez-vous que je lance automatiquement tous les services ? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Lancement automatique..."
    echo "Note: Vous devrez ouvrir des terminaux séparés pour voir les logs individuels"
    
    # Lancer MCP Server en arrière-plan
    echo "▶️  Lancement MCP Server..."
    ./start-mcp-server.sh &
    MCP_PID=$!
    
    sleep 5
    
    # Lancer Agent Server en arrière-plan
    echo "▶️  Lancement Agent Server..."
    ./start-agent-server.sh &
    AGENT_PID=$!
    
    sleep 3
    
    # Lancer Frontend en arrière-plan
    echo "▶️  Lancement Frontend..."
    ./start-frontend.sh &
    FRONTEND_PID=$!
    
    echo ""
    echo "✅ Tous les services sont lancés !"
    echo "🌐 Frontend: http://localhost:3000"
    echo ""
    echo "Pour arrêter tous les services, appuyez sur Ctrl+C"
    
    # Attendre l'interruption
    trap "echo; echo '🛑 Arrêt des services...'; kill $MCP_PID $AGENT_PID $FRONTEND_PID 2>/dev/null; echo '✅ Tous les services arrêtés'; exit" INT
    wait
else
    echo "👍 Lancez les services manuellement dans des terminaux séparés"
fi 