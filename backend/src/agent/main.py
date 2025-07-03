"""
Script principal pour lancer l'agent IA d'inclusion sociale en mode CLI interactif.

Ce module initialise tous les composants nécessaires (configuration, serveur MCP, agent)
et démarre une session de chat interactive dans le terminal.
"""

import asyncio

from pydantic_ai.mcp import MCPServerStreamableHTTP

from .config import Settings
from .agent import create_inclusion_agent


async def main():
    """
    Fonction principale qui initialise et lance l'agent IA en mode interactif.
    
    Cette fonction :
    1. Charge la configuration depuis les variables d'environnement
    2. Crée la connexion au serveur MCP
    3. Instancie l'agent IA spécialisé
    4. Lance une session CLI interactive
    """
    
    # Chargement de la configuration depuis .env
    settings = Settings()
    
    # Création de la connexion au serveur MCP
    mcp_server = MCPServerStreamableHTTP(settings.MCP_SERVER_URL)
    
    # Instanciation de l'agent IA avec la factory
    agent = create_inclusion_agent(mcp_server)
    
    # Lancement de la session CLI interactive avec le contexte MCP
    async with agent.run_mcp_servers():
        await agent.to_cli()


if __name__ == "__main__":
    # Point d'entrée du script - lance la fonction main de manière asynchrone
    asyncio.run(main()) 