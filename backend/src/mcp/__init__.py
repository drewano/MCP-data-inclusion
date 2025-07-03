"""
Module MCP (Model Context Protocol) pour le serveur DataInclusion.

Ce module contient tous les composants nécessaires au fonctionnement
du serveur MCP qui expose l'API data.inclusion.beta.gouv.fr.
"""

from .config import Settings
from .server import main

__all__ = ["Settings", "main"] 