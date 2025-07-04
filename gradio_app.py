#!/usr/bin/env python3
"""
Script principal pour lancer l'interface Gradio de l'agent IA d'inclusion sociale.

Ce script lance une interface web moderne et élégante pour interagir avec 
l'agent IA spécialisé dans l'inclusion sociale en France.

Usage:
    python gradio_app.py                    # Lancer avec les paramètres par défaut
    python gradio_app.py --port 8080        # Lancer sur le port 8080
    python gradio_app.py --share            # Créer un lien public
    python gradio_app.py --agent-url http://localhost:8001  # URL du serveur agent
"""

import sys
import os
import logging

# Ajouter le répertoire src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.gradio_interface import GradioInterface

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Lance l'interface Gradio avec les paramètres de ligne de commande."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="🏠 Interface Gradio pour l'agent IA d'inclusion sociale",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  %(prog)s                                    # Interface sur localhost:7860
  %(prog)s --port 8080                        # Interface sur le port 8080
  %(prog)s --share                            # Créer un lien public partageable
  %(prog)s --agent-url http://agent:8001      # Connexion à un serveur agent distant
  
Pré-requis:
  Les services backend doivent être démarrés avec: docker-compose up
        """
    )
    
    parser.add_argument(
        "--agent-url",
        default="http://localhost:8001",
        help="URL du serveur agent (défaut: http://localhost:8001)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port pour l'interface Gradio (défaut: 7860)"
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Adresse d'écoute (défaut: 0.0.0.0 pour toutes les interfaces)"
    )
    
    parser.add_argument(
        "--share",
        action="store_true",
        help="Créer un lien public partageable via Gradio"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activer le mode debug avec logs détaillés"
    )
    
    args = parser.parse_args()
    
    # Configuration du niveau de logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Mode debug activé")
    
    # Affichage des informations de démarrage
    logger.info("=" * 60)
    logger.info("🚀 Lancement de l'interface Gradio DataInclusion")
    logger.info("=" * 60)
    logger.info(f"📡 URL du serveur agent: {args.agent_url}")
    logger.info(f"🌐 Interface web: http://{args.host}:{args.port}")
    logger.info(f"🔗 Partage public: {'Oui' if args.share else 'Non'}")
    logger.info(f"🐛 Mode debug: {'Oui' if args.debug else 'Non'}")
    logger.info("=" * 60)
    
    try:
        # Créer l'interface Gradio
        interface = GradioInterface(
            agent_url=args.agent_url,
            title="🏠 Assistant IA - Inclusion Sociale en France",
        )
        
        # Lancer l'interface
        logger.info("✅ Interface Gradio initialisée avec succès")
        logger.info("💡 Utilisez Ctrl+C pour arrêter le serveur")
        logger.info("=" * 60)
        
        interface.launch(
            share=args.share,
            server_name=args.host,
            server_port=args.port,
            debug=args.debug
        )
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Arrêt du serveur demandé par l'utilisateur")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du lancement de l'interface: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)
        
    finally:
        logger.info("👋 Interface Gradio fermée")


if __name__ == "__main__":
    main() 