"""
Gestionnaire de cycle de vie pour l'application FastAPI.

Ce module contient la fonction de cycle de vie qui gère l'initialisation
et la finalisation de l'application FastAPI avec l'agent IA.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from pydantic_ai.mcp import MCPServerStreamableHTTP

# Imports locaux
from .config import settings
from ..agent.agent import create_inclusion_agent

# Configuration du logging
logger = logging.getLogger("datainclusion.agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Asynchronous lifecycle manager for a FastAPI application integrating an AI agent.
    
    Handles startup and shutdown procedures, including connecting to an MCP server with retry and exponential backoff logic, initializing the AI agent, ensuring required directories exist, and storing the agent in the application state. Raises a RuntimeError if all connection attempts to the MCP server fail.
    """
    logger.info("🚀 Démarrage de l'application Gradio + FastAPI...")

    # Initialisation du serveur MCP
    mcp_server = MCPServerStreamableHTTP(settings.agent.MCP_SERVER_URL)

    # Création de l'agent avec le serveur MCP
    agent = create_inclusion_agent(mcp_server)

    # Logique de connexion au MCP avec retry et backoff exponentiel
    max_retries = settings.agent.AGENT_MCP_CONNECTION_MAX_RETRIES
    base_delay = settings.agent.AGENT_MCP_CONNECTION_BASE_DELAY
    backoff_multiplier = settings.agent.AGENT_MCP_CONNECTION_BACKOFF_MULTIPLIER

    for attempt in range(max_retries):
        try:
            async with agent.run_mcp_servers():
                # Stocker l'instance de l'agent dans l'état de l'application
                app.state.agent = agent

                # Création des répertoires nécessaires
                Path("feedback_data").mkdir(exist_ok=True)
                Path("exports").mkdir(exist_ok=True)
                Path("logs").mkdir(exist_ok=True)

                logger.info("✅ Application initialisée avec succès")

                # Application prête
                yield

                # Code après yield s'exécute lors du shutdown
                break

        except Exception as e:
            if attempt == max_retries - 1:
                # Dernière tentative échouée
                raise RuntimeError(
                    f"Échec de la connexion au serveur MCP après {max_retries} tentatives: {e}"
                )

            # Calcul du délai avec backoff exponentiel
            delay = base_delay * (backoff_multiplier**attempt)

            logger.warning(
                f"Tentative {attempt + 1}/{max_retries} échouée. Nouvelle tentative dans {delay:.2f}s..."
            )
            await asyncio.sleep(delay)

    # Nettoyage lors du shutdown
    logger.info("🛑 Arrêt de l'application...")
    logger.info("✅ Nettoyage terminé")
