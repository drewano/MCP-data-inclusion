"""
Factory pour créer et configurer l'agent IA d'inclusion sociale.

Ce module contient la fonction factory qui instancie l'agent PydanticAI
avec sa configuration spécialisée pour l'inclusion sociale en France.
"""

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models.openai import OpenAIModel

from .config import Settings


def create_inclusion_agent(mcp_server: MCPServerStreamableHTTP) -> Agent:
    """
    Crée et configure l'agent IA spécialisé dans l'inclusion sociale en France.
    
    Args:
        mcp_server: Instance du serveur MCP pour accéder aux données d'inclusion
        
    Returns:
        Agent configuré pour répondre aux questions sur l'inclusion sociale
    """
    
    # Charger la configuration pour obtenir la clé API
    settings = Settings()
    
    # Utiliser OpenAI au lieu de Gemini pour éviter les problèmes avec les schémas $ref
    # OpenAI gère mieux les schémas JSON complexes avec des références
    model = OpenAIModel(settings.AGENT_MODEL_NAME)
    
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
        mcp_servers=[mcp_server]
    ) 