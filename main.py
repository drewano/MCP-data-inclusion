#!/usr/bin/env python3
"""
Point d'entrée principal pour le serveur Agent DataInclusion.

Ce script lance le serveur web ASGI qui expose l'agent IA d'inclusion sociale
via le protocole Agent-to-Agent (A2A) de Pydantic AI.
"""

import sys
import asyncio
from src.agent.server import main as run_agent_server


if __name__ == "__main__":
    """
    Point d'entrée du script.
    Lance le serveur d'agent web avec gestion d'erreurs appropriée.
    """
    try:
        asyncio.run(run_agent_server())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1) 