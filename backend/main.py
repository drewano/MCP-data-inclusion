#!/usr/bin/env python3
"""
Point d'entrée principal pour le serveur Agent DataInclusion.

Ce script lance le serveur web ASGI qui expose l'agent IA d'inclusion sociale
via le protocole Agent-to-Agent (A2A) de Pydantic AI.
"""

import sys
import uvicorn
from src.agent.server import app
from src.agent.config import Settings


if __name__ == "__main__":
    """
    Point d'entrée du script.
    Lance le serveur d'agent web avec gestion d'erreurs appropriée.
    """
    try:
        settings = Settings()
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=settings.AGENT_PORT,
            reload=False  # Pas de rechargement automatique pour le déploiement
        )
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1) 