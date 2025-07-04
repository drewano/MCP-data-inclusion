#!/bin/bash

# Script de nettoyage pour le projet DataInclusion
# Permet de nettoyer les conteneurs, images, volumes et caches Docker

set -e

echo "🧹 Script de Nettoyage DataInclusion"
echo "====================================="

# Fonction pour afficher l'aide
show_help() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --light     Nettoyage léger (arrêt des conteneurs)"
    echo "  --medium    Nettoyage moyen (+ suppression des volumes)"
    echo "  --deep      Nettoyage profond (+ images et cache Docker)"
    echo "  --help      Afficher cette aide"
    echo ""
    echo "Sans option: nettoyage interactif"
}

# Fonction de nettoyage léger
light_clean() {
    echo "🔄 Nettoyage léger en cours..."
    echo "  • Arrêt des conteneurs..."
    docker-compose down 2>/dev/null || true
    echo "  ✅ Conteneurs arrêtés"
}

# Fonction de nettoyage moyen
medium_clean() {
    echo "🔄 Nettoyage moyen en cours..."
    echo "  • Arrêt des conteneurs et suppression des volumes..."
    docker-compose down --volumes --remove-orphans 2>/dev/null || true
    echo "  ✅ Conteneurs et volumes supprimés"
}

# Fonction de nettoyage profond
deep_clean() {
    echo "🔄 Nettoyage profond en cours..."
    echo "  • Arrêt des conteneurs et suppression des volumes..."
    docker-compose down --volumes --remove-orphans 2>/dev/null || true
    
    echo "  • Suppression des images du projet..."
    # Supprimer uniquement les images de ce projet
    docker images --format "{{.Repository}}:{{.Tag}}" | grep "mcp-data-inclusion" | xargs -r docker rmi 2>/dev/null || true
    
    echo "  • Nettoyage du système Docker..."
    docker system prune -f --volumes 2>/dev/null || true
    
    echo "  • Nettoyage des images non utilisées..."
    docker image prune -f 2>/dev/null || true
    
    echo "  ✅ Nettoyage profond terminé"
}

# Fonction de nettoyage interactif
interactive_clean() {
    echo "Choisissez le type de nettoyage :"
    echo ""
    echo "1) Léger    - Arrêter les conteneurs uniquement"
    echo "2) Moyen    - Arrêter les conteneurs + supprimer les volumes"
    echo "3) Profond  - Tout nettoyer (conteneurs, volumes, images, cache)"
    echo "4) Annuler"
    echo ""
    read -p "Votre choix [1-4] : " choice
    
    case $choice in
        1)
            light_clean
            ;;
        2)
            medium_clean
            ;;
        3)
            echo ""
            echo "⚠️  ATTENTION: Le nettoyage profond va supprimer TOUTES les images Docker"
            echo "et volumes non utilisés de votre système, pas seulement ce projet."
            read -p "Êtes-vous sûr ? [y/N] : " confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                deep_clean
            else
                echo "❌ Nettoyage annulé"
                exit 0
            fi
            ;;
        4|*)
            echo "❌ Nettoyage annulé"
            exit 0
            ;;
    esac
}

# Afficher les statistiques avant nettoyage
show_before_stats() {
    echo ""
    echo "📊 État avant nettoyage :"
    echo "  • Conteneurs en cours d'exécution :"
    docker ps --format "    {{.Names}} ({{.Status}})" 2>/dev/null || echo "    Aucun"
    echo "  • Volumes Docker :"
    docker volume ls -q | wc -l | sed 's/^/    /' 2>/dev/null || echo "    0"
    echo "  • Images Docker :"
    docker images -q | wc -l | sed 's/^/    /' 2>/dev/null || echo "    0"
    echo ""
}

# Afficher les statistiques après nettoyage
show_after_stats() {
    echo ""
    echo "📊 État après nettoyage :"
    echo "  • Conteneurs en cours d'exécution :"
    docker ps --format "    {{.Names}} ({{.Status}})" 2>/dev/null || echo "    Aucun"
    echo "  • Volumes Docker restants :"
    docker volume ls -q | wc -l | sed 's/^/    /' 2>/dev/null || echo "    0"
    echo "  • Images Docker restantes :"
    docker images -q | wc -l | sed 's/^/    /' 2>/dev/null || echo "    0"
    echo ""
}

# Vérifier si Docker est disponible
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé ou n'est pas accessible."
    exit 1
fi

# Traitement des arguments
case "$1" in
    --light)
        show_before_stats
        light_clean
        show_after_stats
        ;;
    --medium)
        show_before_stats
        medium_clean
        show_after_stats
        ;;
    --deep)
        show_before_stats
        echo ""
        echo "⚠️  ATTENTION: Le nettoyage profond va supprimer TOUTES les images Docker"
        echo "et volumes non utilisés de votre système, pas seulement ce projet."
        read -p "Êtes-vous sûr ? [y/N] : " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            deep_clean
            show_after_stats
        else
            echo "❌ Nettoyage annulé"
            exit 0
        fi
        ;;
    --help)
        show_help
        exit 0
        ;;
    "")
        show_before_stats
        interactive_clean
        show_after_stats
        ;;
    *)
        echo "❌ Option inconnue: $1"
        echo ""
        show_help
        exit 1
        ;;
esac

echo "✅ Nettoyage terminé avec succès !"
echo ""
echo "💡 Pour relancer l'application :"
echo "   ./start.sh"
echo ""
echo "📚 Pour plus d'informations :"
echo "   cat QUICK_START.md" 