import logging
import httpx
from fastmcp import FastMCP
from fastmcp.utilities.openapi import HTTPRoute


async def inspect_mcp_components(mcp_instance: FastMCP, logger: logging.Logger):
    """Inspecte et affiche les composants MCP (outils, ressources, templates)."""
    logger.info("--- Inspecting MCP Components ---")
    tools = await mcp_instance.get_tools()
    resources = await mcp_instance.get_resources()
    templates = await mcp_instance.get_resource_templates()

    # Séparer les outils activés et désactivés
    enabled_tools = [t for t in tools.values() if t.enabled and t.name is not None]
    disabled_tools = [t for t in tools.values() if not t.enabled and t.name is not None]
    
    logger.info(f"{len(tools)} Total Tool(s) found ({len(enabled_tools)} enabled, {len(disabled_tools)} disabled):")
    if enabled_tools:
        logger.info(f"  Enabled Tools: {', '.join(sorted([t.name for t in enabled_tools]))}")
    else:
        logger.info("  No enabled tools found.")
    
    if disabled_tools:
        logger.debug(f"  Disabled Tools: {', '.join(sorted([t.name for t in disabled_tools]))}")

    logger.info(f"{len(resources)} Resource(s) found:")
    if resources:
        logger.info(f"  Names: {', '.join(sorted([r.name for r in resources.values() if r.name is not None]))}")
    else:
        logger.info("  No resources generated.")

    logger.info(f"{len(templates)} Resource Template(s) found:")
    if templates:
        logger.info(f"  Names: {', '.join(sorted([t.name for t in templates.values() if t.name is not None]))}")
    else:
        logger.info("  No resource templates generated.")
    logger.info("--- End of MCP Components Inspection ---")


def create_api_client(base_url: str, logger: logging.Logger, api_key: str | None = None) -> httpx.AsyncClient:
    """Crée un client HTTP avec authentification pour l'API Data Inclusion.
    
    Args:
        base_url: L'URL de base de l'API
        logger: Instance du logger pour les messages
        api_key: Clé d'API optionnelle pour l'authentification
        
    Returns:
        httpx.AsyncClient: Client HTTP configuré avec les headers d'authentification
    """
    headers = {}
    
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        logger.info(f"Using DATA_INCLUSION_API_KEY from configuration (key: ***{api_key[-4:]})")
    else:
        logger.warning("DATA_INCLUSION_API_KEY not set in configuration.")
        logger.warning("Some API endpoints may be publicly accessible, but authenticated endpoints will fail.")
        logger.warning("Please set DATA_INCLUSION_API_KEY in your .env file if you have an API key.")
    
    # Ajout d'headers par défaut
    headers.update({
        "User-Agent": "DataInclusion-MCP-Server/1.0",
        "Accept": "application/json"
    })
    
    return httpx.AsyncClient(
        base_url=base_url, 
        headers=headers,
        timeout=30.0  # Timeout de 30 secondes
    )


def deep_clean_schema(schema: dict) -> None:
    """Nettoie récursivement un schéma JSON en supprimant tous les champs "title".
    
    Cette fonction parcourt récursivement un dictionnaire représentant un schéma JSON
    et supprime toutes les clés "title" trouvées, y compris dans les dictionnaires 
    imbriqués et les listes de dictionnaires.
    
    Args:
        schema: Dictionnaire représentant un schéma JSON à nettoyer
        
    Note:
        Cette fonction modifie le dictionnaire en place et ne retourne rien.
    """
    if not isinstance(schema, dict):
        return
    
    # Collecter les clés "title" à supprimer pour éviter de modifier 
    # le dictionnaire pendant l'itération
    keys_to_remove = []
    
    for key, value in schema.items():
        if key == "title":
            keys_to_remove.append(key)
        elif isinstance(value, dict):
            # Nettoyer récursivement les dictionnaires imbriqués
            deep_clean_schema(value)
        elif isinstance(value, list):
            # Nettoyer récursivement les éléments de liste qui sont des dictionnaires
            for item in value:
                if isinstance(item, dict):
                    deep_clean_schema(item)
    
    # Supprimer toutes les clés "title" collectées
    for key in keys_to_remove:
        del schema[key]


async def find_route_by_id(operation_id: str, routes: list[HTTPRoute]) -> HTTPRoute | None:
    """
    Recherche un objet HTTPRoute par son operation_id.
    
    Cette fonction parcourt une liste d'objets HTTPRoute et retourne le premier
    objet dont l'attribut operation_id correspond à l'operation_id fourni.
    
    Args:
        operation_id: L'identifiant d'opération à rechercher
        routes: La liste des objets HTTPRoute à parcourir
        
    Returns:
        HTTPRoute | None: L'objet HTTPRoute correspondant ou None si aucune correspondance n'est trouvée
    """
    for route in routes:
        if hasattr(route, 'operation_id') and route.operation_id == operation_id:
            return route
    return None
