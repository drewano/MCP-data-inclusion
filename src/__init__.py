"""
Package src - DataInclusion MCP Server

Ce package contient :
- mcp_server : Composants du serveur MCP (Model Context Protocol)
- agent : Composants d'automatisation et d'aide (futures fonctionnalités)
"""

# Exposer les composants principaux du module MCP
from .mcp_server import Settings, main

__all__ = ["Settings", "main"] 