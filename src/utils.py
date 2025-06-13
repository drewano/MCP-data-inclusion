import os
import httpx
from fastmcp import FastMCP


async def inspect_mcp_components(mcp_instance: FastMCP):
    """Inspecte et affiche les composants MCP (outils, ressources, templates)."""
    print("\n--- Inspecting MCP Components ---")
    tools = await mcp_instance.get_tools()
    resources = await mcp_instance.get_resources()
    templates = await mcp_instance.get_resource_templates()

    print(f"{len(tools)} Tool(s) found:")
    if tools:
        print(f"  Names: {', '.join(sorted([t.name for t in tools.values() if t.name is not None]))}")
    else:
        print("  No tools generated.")

    print(f"{len(resources)} Resource(s) found:")
    if resources:
        print(f"  Names: {', '.join(sorted([r.name for r in resources.values() if r.name is not None]))}")
    else:
        print("  No resources generated.")

    print(f"{len(templates)} Resource Template(s) found:")
    if templates:
        print(f"  Names: {', '.join(sorted([t.name for t in templates.values() if t.name is not None]))}")
    else:
        print("  No resource templates generated.")
    print("--- End of MCP Components Inspection ---\n")


def create_api_client(base_url: str) -> httpx.AsyncClient:
    """Crée un client HTTP avec authentification pour l'API Data Inclusion.
    
    Args:
        base_url: L'URL de base de l'API
        
    Returns:
        httpx.AsyncClient: Client HTTP configuré avec les headers d'authentification
    """
    headers = {}
    api_key = os.getenv("DATA_INCLUSION_API_KEY")
    
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        print(f"✅ Using DATA_INCLUSION_API_KEY from environment variable (key: ***{api_key[-4:]})")
    else:
        print("⚠️  Warning: DATA_INCLUSION_API_KEY environment variable not set.")
        print("   Some API endpoints may be publicly accessible, but authenticated endpoints will fail.")
        print("   Please set DATA_INCLUSION_API_KEY in your .env file if you have an API key.")
    
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
