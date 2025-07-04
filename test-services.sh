#!/bin/bash

echo "🧪 Test des services MCP Data Inclusion"
echo "======================================"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction pour tester un service
test_service() {
    local name="$1"
    local url="$2"
    
    echo -n "Testing $name... "
    
    if curl -s --max-time 5 "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        return 1
    fi
}

# Fonction pour tester un service avec une réponse JSON
test_json_service() {
    local name="$1"
    local url="$2"
    
    echo -n "Testing $name... "
    
    response=$(curl -s --max-time 5 -H "Accept: application/json" "$url" 2>/dev/null)
    
    if [ $? -eq 0 ] && echo "$response" | jq empty 2>/dev/null; then
        echo -e "${GREEN}✓ OK${NC}"
        echo "  Response sample: $(echo "$response" | jq -r '.name // .message // "OK"' 2>/dev/null | head -c 50)..."
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        if [ -n "$response" ]; then
            echo "  Error: $response"
        fi
        return 1
    fi
}

echo ""
echo "🔍 Vérification des services..."

# Tester les services principaux
test_service "Frontend (Next.js)" "http://localhost:3000"
test_json_service "Agent Server" "http://localhost:8001/.well-known/agent.json"
test_service "MCP Server Health" "http://localhost:8000/health"

echo ""
echo "🐳 Vérification des conteneurs Docker..."

# Vérifier que tous les conteneurs sont en cours d'exécution
containers=("frontend" "agent_server" "mcp_server" "redis")
all_running=true

for container in "${containers[@]}"; do
    echo -n "Checking container $container... "
    if docker compose ps | grep -q "${container}.*Up"; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not running${NC}"
        all_running=false
    fi
done

echo ""
echo "🔧 Informations de débogage..."

# Afficher les variables d'environnement importantes
echo "Environment variables:"
echo "  NODE_ENV: ${NODE_ENV:-"not set"}"
echo "  TRANSPORT: ${TRANSPORT:-"not set"}"
echo "  MCP_PORT: ${MCP_PORT:-"not set"}"

# Afficher les ports en écoute
echo ""
echo "Ports en écoute:"
netstat -tuln 2>/dev/null | grep -E ':(3000|8000|8001|6379)' || echo "  Commande netstat non disponible"

if [ "$all_running" = true ]; then
    echo ""
    echo -e "${GREEN}✅ Tous les services semblent fonctionner correctement!${NC}"
    echo ""
    echo "📱 Accès aux services:"
    echo "  Frontend: http://localhost:3000"
    echo "  Agent API: http://localhost:8001"
    echo "  MCP Server: http://localhost:8000"
    echo ""
    echo "🔍 Pour voir les logs:"
    echo "  docker compose logs -f"
else
    echo ""
    echo -e "${RED}❌ Certains services ne fonctionnent pas correctement.${NC}"
    echo ""
    echo "🔍 Commandes de débogage:"
    echo "  docker compose ps                    # Voir l'état des conteneurs"
    echo "  docker compose logs [service_name]   # Voir les logs d'un service"
    echo "  docker compose up --build            # Redémarrer tous les services"
fi 