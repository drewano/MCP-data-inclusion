"""
Configuration management for the AI Agent using Pydantic Settings.

Ce module centralise la configuration de l'agent IA en utilisant
Pydantic Settings pour une gestion robuste et typée des variables d'environnement.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration de l'agent IA basée sur Pydantic Settings.
    
    Cette classe charge automatiquement les variables d'environnement
    depuis le fichier .env et valide leur type.
    """
    
    # Configuration de l'API OpenAI (recommandé pour éviter les problèmes de schéma $ref)
    OPENAI_API_KEY: str = ""
    
    # Nom du modèle OpenAI à utiliser pour l'agent
    AGENT_MODEL_NAME: str = 'gpt-4.1'
    
    # Configuration de l'API Gemini (optionnel, peut causer des problèmes avec les schémas $ref)
    GEMINI_API_KEY: str | None = None
    
    # Configuration de connexion au serveur MCP
    # Utilise le nom du service Docker pour la communication inter-conteneurs
    MCP_SERVER_URL: str = "http://mcp_server:8000/mcp"
    
    # Port du serveur agent
    AGENT_PORT: int = 8001
    
    # Configuration Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Configuration de la logique de retry pour la connexion MCP
    # Nombre maximum de tentatives de connexion au serveur MCP
    AGENT_MCP_CONNECTION_MAX_RETRIES: int = 10
    
    # Délai initial en secondes avant la première nouvelle tentative
    AGENT_MCP_CONNECTION_BASE_DELAY: float = 1.0
    
    # Multiplicateur pour le backoff exponentiel entre les tentatives
    AGENT_MCP_CONNECTION_BACKOFF_MULTIPLIER: float = 2.0
    
    @property
    def REDIS_URL(self) -> str:
        """
        Construit l'URL de connexion Redis.
        
        Returns:
            str: URL de connexion Redis au format redis://host:port/db
        """
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Configuration Pydantic Settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore les variables d'environnement non définies
    ) 