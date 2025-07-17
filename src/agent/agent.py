"""
Factory pour créer et configurer l'agent IA d'inclusion sociale.

Ce module contient la fonction factory qui instancie l'agent PydanticAI
avec sa configuration spécialisée pour l'inclusion sociale en France.
"""

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models.openai import OpenAIModel

from ..core.config import settings


def create_inclusion_agent(mcp_server: MCPServerStreamableHTTP) -> Agent:
    """
    Instantiate and configure an AI agent specialized in social inclusion services and resources in France.
    
    Parameters:
        mcp_server (MCPServerStreamableHTTP): The MCP server instance providing access to inclusion-related data.
    
    Returns:
        Agent: An agent configured to answer questions about social inclusion, aid structures, and available resources in France.
    """

    # Utiliser OpenAI au lieu de Gemini pour éviter les problèmes avec les schémas $ref
    # OpenAI gère mieux les schémas JSON complexes avec des références
    model = OpenAIModel(settings.agent.AGENT_MODEL_NAME)

    return Agent(
        # Modèle OpenAI qui supporte mieux les schémas JSON complexes
        model=model,
        # Prompt système définissant le rôle et les instructions de l'agent
        system_prompt=(
            "Tu es un assistant expert de l'inclusion sociale en France. "
            "Utilise les outils disponibles pour répondre aux questions sur les "
            "structures et services d'aide. Sois précis et factuel. "
            "Ton rôle est d'aider les utilisateurs à trouver des informations "
            "sur les services d'inclusion, les structures d'aide, et les "
            "ressources disponibles sur le territoire français."
        ),
        # Configuration des serveurs MCP pour accéder aux données
        mcp_servers=[mcp_server],
    )
