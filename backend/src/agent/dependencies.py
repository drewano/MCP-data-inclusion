"""
Dependencies for the AI Agent.

Ce module définit les dépendances de l'agent IA en utilisant dataclass
pour une injection de dépendances propre et typée, selon les bonnes pratiques de Pydantic-AI.
"""

from dataclasses import dataclass
from pydantic_ai.mcp import MCPServerStreamableHTTP


@dataclass
class AgentDependencies:
    """
    Classe de dépendances pour l'agent IA.
    
    Cette dataclass contient toutes les dépendances nécessaires
    au fonctionnement de l'agent, notamment le client MCP.
    """
    
    mcp_server: MCPServerStreamableHTTP 