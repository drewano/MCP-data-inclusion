"""
Configuration management using Pydantic Settings.

Ce module centralise toute la configuration de l'application en utilisant
Pydantic Settings pour une gestion robuste et typée des variables d'environnement.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration de l'application basée sur Pydantic Settings.
    
    Cette classe charge automatiquement les variables d'environnement
    depuis le fichier .env et valide leur type.
    """
    
    # Configuration de l'API OpenAPI
    OPENAPI_URL: str = "https://api.data.inclusion.beta.gouv.fr/api/openapi.json"
    
    # Configuration du serveur MCP
    MCP_SERVER_NAME: str = "DataInclusionAPI"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8000
    MCP_API_PATH: str = "/mcp"
    
    # Clés d'API et authentification
    DATA_INCLUSION_API_KEY: str = ""
    MCP_SERVER_SECRET_KEY: str | None = None
    
    # Configuration Pydantic Settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore les variables d'environnement non définies
    ) 