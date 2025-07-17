import logging
import httpx
from fastmcp import FastMCP
from fastmcp.utilities.openapi import HTTPRoute


async def inspect_mcp_components(mcp_instance: FastMCP, logger: logging.Logger):
    """
    Asynchronously logs detailed information about MCP tools, resources, and resource templates from a FastMCP instance.
    
    Retrieves and categorizes tools as enabled or disabled, then logs counts and names for tools, resources, and resource templates. This function is intended for inspection and debugging purposes and does not return a value.
    """
    logger.info("--- Inspecting MCP Components ---")
    tools = await mcp_instance.get_tools()
    resources = await mcp_instance.get_resources()
    templates = await mcp_instance.get_resource_templates()

    # Séparer les outils activés et désactivés
    enabled_tools = [t for t in tools.values() if t.enabled and t.name is not None]
    disabled_tools = [t for t in tools.values() if not t.enabled and t.name is not None]

    logger.info(
        f"{len(tools)} Total Tool(s) found ({len(enabled_tools)} enabled, {len(disabled_tools)} disabled):"
    )
    if enabled_tools:
        logger.info(
            f"  Enabled Tools: {', '.join(sorted([t.name for t in enabled_tools]))}"
        )
    else:
        logger.info("  No enabled tools found.")

    if disabled_tools:
        logger.debug(
            f"  Disabled Tools: {', '.join(sorted([t.name for t in disabled_tools]))}"
        )

    logger.info(f"{len(resources)} Resource(s) found:")
    if resources:
        logger.info(
            f"  Names: {', '.join(sorted([r.name for r in resources.values() if r.name is not None]))}"
        )
    else:
        logger.info("  No resources generated.")

    logger.info(f"{len(templates)} Resource Template(s) found:")
    if templates:
        logger.info(
            f"  Names: {', '.join(sorted([t.name for t in templates.values() if t.name is not None]))}"
        )
    else:
        logger.info("  No resource templates generated.")
    logger.info("--- End of MCP Components Inspection ---")


def create_api_client(
    base_url: str, logger: logging.Logger, api_key: str | None = None
) -> httpx.AsyncClient:
    """
    Create and return an asynchronous HTTP client configured for API access.
    
    If an API key is provided, the client includes an Authorization header for authenticated requests. Default headers and a 30-second timeout are set. Logs warnings if no API key is supplied.
    
    Returns:
        httpx.AsyncClient: Configured asynchronous HTTP client for API communication.
    """
    headers = {}

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        logger.info(
            f"Using DATA_INCLUSION_API_KEY from configuration (key: ***{api_key[-4:]})"
        )
    else:
        logger.warning("DATA_INCLUSION_API_KEY not set in configuration.")
        logger.warning(
            "Some API endpoints may be publicly accessible, but authenticated endpoints will fail."
        )
        logger.warning(
            "Please set DATA_INCLUSION_API_KEY in your .env file if you have an API key."
        )

    # Ajout d'headers par défaut
    headers.update(
        {"User-Agent": "DataInclusion-MCP-Server/1.0", "Accept": "application/json"}
    )

    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=30.0,  # Timeout de 30 secondes
    )


def deep_clean_schema(schema: dict) -> None:
    """
    Recursively removes all "title" keys from a JSON schema dictionary and its nested structures.
    
    This function traverses the input dictionary in place, deleting any key named "title" found at any level, including within nested dictionaries and lists of dictionaries.
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


async def find_route_by_id(
    operation_id: str, routes: list[HTTPRoute]
) -> HTTPRoute | None:
    """
    Searches for an HTTPRoute object in a list by its operation_id.
    
    Returns the first HTTPRoute whose operation_id matches the given string, or None if no match is found.
    """
    for route in routes:
        if hasattr(route, "operation_id") and route.operation_id == operation_id:
            return route
    return None
