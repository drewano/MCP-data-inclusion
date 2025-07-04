"""
DataInclusion MCP Server

Ce serveur MCP expose l'API data.inclusion.beta.gouv.fr via le protocole Model Context Protocol.
Il transforme automatiquement les endpoints OpenAPI en outils MCP.
"""

import asyncio
import json
import logging
import os
import httpx
from fastmcp import FastMCP
from fastmcp.tools import Tool
from fastmcp.tools.tool_transform import ArgTransform
from fastmcp.server.openapi import RouteMap, MCPType
from fastmcp.server.auth import BearerAuthProvider
from fastmcp.server.auth.providers.bearer import RSAKeyPair
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.openapi import parse_openapi_to_http_routes, HTTPRoute
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from .config import Settings
from .utils import inspect_mcp_components, create_api_client, deep_clean_schema, find_route_by_id
from .logging_config import setup_logging
from .middleware import ErrorHandlingMiddleware, TimingMiddleware

def limit_page_size_in_spec(spec: dict, logger: logging.Logger, max_size: int = 25) -> dict:
    """
    Modifie la spécification OpenAPI pour limiter la taille des pages.

    Cette fonction parcourt les points de terminaison pertinents et ajuste le paramètre
    'size' pour qu'il ait une valeur maximale et par défaut de `max_size`.

    Args:
        spec: Le dictionnaire de la spécification OpenAPI.
        logger: Instance du logger pour les messages.
        max_size: La taille maximale à définir pour les résultats.

    Returns:
        Le dictionnaire de la spécification modifié.
    """
    paths_to_modify = [
        "/api/v0/structures",
        "/api/v0/services",
        "/api/v0/search/services",
    ]

    logger.info(f"Applying page size limit (max_size={max_size}) to spec...")

    for path in paths_to_modify:
        if path in spec["paths"] and "get" in spec["paths"][path]:
            params = spec["paths"][path]["get"].get("parameters", [])
            for param in params:
                if param.get("name") == "size":
                    param["schema"]["maximum"] = max_size
                    param["schema"]["default"] = max_size
                    logger.info(f"  - Limited 'size' parameter for endpoint: GET {path}")
    
    return spec


def customize_for_gemini(route, component, logger: logging.Logger):
    """
    Simplifie les schémas d'un composant pour une meilleure compatibilité
    avec les modèles stricts comme Gemini, en retirant les titres.
    """
    tool_name = getattr(component, 'name', 'Unknown')
    cleaned_schemas = []
    
    # Nettoyer le schéma d'entrée
    if hasattr(component, 'input_schema') and component.input_schema:
        deep_clean_schema(component.input_schema)
        cleaned_schemas.append("input schema")
        logger.info(f"Input schema cleaned for tool: {tool_name}")
    
    # Nettoyer le schéma de sortie
    if hasattr(component, 'output_schema') and component.output_schema:
        deep_clean_schema(component.output_schema)
        cleaned_schemas.append("output schema")
        logger.info(f"Output schema cleaned for tool: {tool_name}")
    
    # Message de résumé si des schémas ont été nettoyés
    if cleaned_schemas:
        logger.info(f"Schema cleaning completed for tool '{tool_name}': {', '.join(cleaned_schemas)}")
    else:
        logger.debug(f"No schemas found to clean for tool: {tool_name}")


def discover_and_customize(route: HTTPRoute, component: FastMCPComponent, logger: logging.Logger, op_id_map: dict[str, str]):
    """
    Personnalise le composant pour Gemini et découvre le nom de l'outil généré.
    """
    # Appel de la fonction de personnalisation existante
    customize_for_gemini(route, component, logger)
    
    # Découverte du nom de l'outil et stockage dans la map
    if hasattr(route, 'operation_id') and route.operation_id and hasattr(component, 'name') and component.name:
        op_id_map[route.operation_id] = component.name


async def main():
    """
    Fonction principale qui configure et lance le serveur MCP.
    
    Cette fonction :
    1. Charge la configuration
    2. Charge la spécification OpenAPI
    3. Crée un client HTTP authentifié
    4. Configure le serveur MCP avec des noms d'outils personnalisés
    5. Lance le serveur avec le transport SSE
    """
    
    # === 0. CHARGEMENT DE LA CONFIGURATION ===
    settings = Settings()
    
    # Dictionnaire pour stocker la correspondance entre operation_id et noms d'outils générés
    op_id_to_mangled_name: dict[str, str] = {}
    
    # === 1. CONFIGURATION DU LOGGING ===
    logger = setup_logging()
    
    api_client = None
    
    try:
        # === 2. CHARGEMENT DE LA SPÉCIFICATION OPENAPI VIA HTTP ===
        logger.info(f"Loading OpenAPI specification from URL: '{settings.OPENAPI_URL}'...")
        
        try:
            # On a besoin d'importer httpx si ce n'est pas déjà fait en haut du fichier
            
            async with httpx.AsyncClient() as client:
                response = await client.get(settings.OPENAPI_URL)
                response.raise_for_status()  # Lève une exception si le statut n'est pas 2xx
                openapi_spec = response.json()
            
            api_title = openapi_spec.get("info", {}).get("title", "Unknown API")
            logger.info(f"Successfully loaded OpenAPI spec: '{api_title}'")
            
            # === PRÉ-PARSING DE LA SPÉCIFICATION OPENAPI ===
            logger.info("Parsing OpenAPI specification to HTTP routes...")
            http_routes = parse_openapi_to_http_routes(openapi_spec)
            logger.info(f"Successfully parsed {len(http_routes)} HTTP routes from OpenAPI specification")
            
            # === MODIFICATION DES LIMITES DE PAGINATION ===
            # Limite la taille des pages pour les outils de listing à 25 éléments maximum
            # Cela s'applique aux outils: list_all_structures, list_all_services, search_services
            logger.info("Applying pagination limits to data-listing endpoints...")
            openapi_spec = limit_page_size_in_spec(openapi_spec, logger=logger, max_size=25)
            
        except httpx.RequestError as e:
            logger.error(f"Failed to fetch OpenAPI specification from '{settings.OPENAPI_URL}'.")
            logger.error(f"Details: {e}")
            return
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in the response from '{settings.OPENAPI_URL}'.")
            logger.error(f"Details: {e}")
            return

        # === 3. DÉTERMINATION DE L'URL DE BASE ===
        servers = openapi_spec.get("servers", [])
        if servers and isinstance(servers, list) and len(servers) > 0 and "url" in servers[0]:
            base_url = servers[0]["url"]
            logger.info(f"Using base URL from OpenAPI spec: {base_url}")
        else:
            base_url = "http://localhost:8000"
            logger.warning("No servers section found in OpenAPI spec.")
            logger.warning(f"Using default base URL: {base_url}")

        # === 4. CRÉATION DU CLIENT HTTP AUTHENTIFIÉ ===
        logger.info("Configuring HTTP client with authentication...")
        api_client = create_api_client(base_url, logger, settings.DATA_INCLUSION_API_KEY)

        # === 5. CONFIGURATION DES NOMS D'OUTILS PERSONNALISÉS ===
        logger.info("Configuring custom tool names...")
        
        # Mapping des noms d'opérations OpenAPI vers des noms d'outils MCP plus conviviaux
        # Note: Noms courts pour respecter la limite de 60 caractères de FastMCP
        custom_mcp_tool_names = {
            # Endpoints de Structures
            "list_structures_endpoint_api_v0_structures_get": "list_all_structures",
            "retrieve_structure_endpoint_api_v0_structures__source___id__get": "get_structure_details",

            # Endpoints de Sources
            "list_sources_endpoint_api_v0_sources_get": "list_all_sources",

            # Endpoints de Services
            "list_services_endpoint_api_v0_services_get": "list_all_services",
            "retrieve_service_endpoint_api_v0_services__source___id__get": "get_service_details",
            "search_services_endpoint_api_v0_search_services_get": "search_services",

            # Endpoints de Documentation
            "as_dict_list_api_v0_doc_labels_nationaux_get": "doc_list_labels_nationaux",
            "as_dict_list_api_v0_doc_thematiques_get": "doc_list_thematiques",
            "as_dict_list_api_v0_doc_typologies_services_get": "doc_list_typologies_services",
            "as_dict_list_api_v0_doc_frais_get": "doc_list_frais",
            "as_dict_list_api_v0_doc_profils_get": "doc_list_profils_publics",
            "as_dict_list_api_v0_doc_typologies_structures_get": "doc_list_typologies_structures",
            "as_dict_list_api_v0_doc_modes_accueil_get": "doc_list_modes_accueil",
            
            # Endpoints modes_orientation (NOMS RACCOURCIS pour respecter limite 60 caractères)
            "as_dict_list_api_v0_doc_modes_orientation_accompagnateur_get": "doc_modes_orient_accomp",
            "as_dict_list_api_v0_doc_modes_orientation_beneficiaire_get": "doc_modes_orient_benef",
        }

        # === 6. CONFIGURATION DES ROUTES MCP ===
        logger.info("Configuring route mappings...")
        
        # Configuration pour mapper tous les endpoints GET comme des outils MCP
        custom_route_maps = [
            RouteMap(methods=["GET"], pattern=r".*", mcp_type=MCPType.TOOL),
        ]

        # === 7. CONFIGURATION DE L'AUTHENTIFICATION ===
        logger.info("Configuring server authentication...")
        
        # Lecture de la clé secrète depuis la configuration
        secret_key = settings.MCP_SERVER_SECRET_KEY
        auth_provider = None
        
        if secret_key and secret_key.strip():
            logger.info("Secret key found - configuring Bearer Token authentication...")
            try:
                # Si la clé ressemble à une clé RSA privée PEM, l'utiliser directement
                if secret_key.strip().startswith("-----BEGIN") and "PRIVATE KEY" in secret_key:
                    # Utiliser la clé privée pour créer une paire de clés
                    from cryptography.hazmat.primitives import serialization
                    private_key = serialization.load_pem_private_key(
                        secret_key.encode(), password=None
                    )
                    public_key_pem = private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    ).decode()
                    
                    auth_provider = BearerAuthProvider(
                        public_key=public_key_pem,
                        audience="datainclusion-mcp-client"
                    )
                else:
                    # Utiliser la clé comme seed pour générer une paire de clés déterministe
                    # Pour des raisons de simplicité, on génère une nouvelle paire de clés
                    key_pair = RSAKeyPair.generate()
                    
                    auth_provider = BearerAuthProvider(
                        public_key=key_pair.public_key,
                        audience="datainclusion-mcp-client"
                    )
                    
                    # Log du token de test (UNIQUEMENT pour le développement)
                    test_token = key_pair.create_token(
                        audience="datainclusion-mcp-client",
                        subject="test-user",
                        expires_in_seconds=3600
                    )
                    logger.info(f"🔑 Test Bearer Token (for development): {test_token}")
                
                logger.info("✓ Bearer Token authentication configured successfully")
                logger.info("   - Audience: datainclusion-mcp-client")
                logger.info("   - Server will require valid Bearer tokens for access")
                
            except Exception as e:
                logger.error(f"Failed to configure authentication: {e}")
                logger.warning("Continuing without authentication...")
                auth_provider = None
        else:
            logger.warning("MCP_SERVER_SECRET_KEY not set - server will run WITHOUT authentication")
            logger.warning("⚠️  All clients will have unrestricted access to the server")

        # === 8. CRÉATION DU SERVEUR MCP ===
        logger.info(f"Creating FastMCP server '{settings.MCP_SERVER_NAME}'...")
        
        mcp_server = FastMCP.from_openapi(
            openapi_spec=openapi_spec,
            client=api_client,
            name=settings.MCP_SERVER_NAME,
            route_maps=custom_route_maps,
            auth=auth_provider,
            mcp_component_fn=lambda route, component: discover_and_customize(route, component, logger, op_id_to_mangled_name)
        )
        
        logger.info(f"FastMCP server '{mcp_server.name}' created successfully!")
        logger.info("   - Custom GET-to-Tool mapping applied")

        # === 8.5. AJOUT DE L'ENDPOINT DE SANTÉ ===
        @mcp_server.custom_route("/health", methods=["GET"])
        async def health_check(request: Request) -> PlainTextResponse:
            """A simple health check endpoint."""
            return PlainTextResponse("OK", status_code=200)
        logger.info("   - Health check endpoint (/health) added successfully")

        # === 9. AJOUT DES MIDDLEWARES ===
        logger.info("Adding middleware stack...")
        
        # Ajouter le middleware de gestion d'erreurs EN PREMIER
        # Il doit capturer toutes les erreurs des autres middlewares
        error_handling_middleware = ErrorHandlingMiddleware(logger)
        mcp_server.add_middleware(error_handling_middleware)
        logger.info("   - Error handling middleware added successfully")
        
        # Ajouter le middleware de timing APRÈS la gestion d'erreurs
        timing_middleware = TimingMiddleware(logger)
        mcp_server.add_middleware(timing_middleware)
        logger.info("   - Timing middleware added successfully")

        # === 10. RENOMMAGE ET ENRICHISSEMENT AVANCÉ DES OUTILS ===
        logger.info("Applying advanced tool transformations using Tool.from_tool()...")
        
        successful_renames = 0
        total_tools = len(custom_mcp_tool_names)
        
        for original_name, new_name in custom_mcp_tool_names.items():
            # Rechercher la route correspondante dans les données OpenAPI
            route = await find_route_by_id(original_name, http_routes)
            if route is None:
                logger.warning(f"  ✗ Route not found for operation_id: '{original_name}' - skipping transformation")
                continue
            
            # Utilise la map pour obtenir le nom de l'outil généré par FastMCP
            mangled_tool_name = op_id_to_mangled_name.get(original_name)
            if not mangled_tool_name:
                logger.warning(f"  ✗ Could not find a generated tool for operation_id: '{original_name}' - skipping transformation")
                continue
            
            try:
                # Récupérer l'outil original en utilisant son nom "manglé"
                original_tool = await mcp_server.get_tool(mangled_tool_name)
                if not original_tool:
                    logger.warning(f"  ✗ Tool not found: '{mangled_tool_name}' (may have been renamed during OpenAPI processing)")
                    continue
                
                # === ENRICHISSEMENT DES ARGUMENTS ===
                arg_transforms = {}
                param_count = 0
                
                # Enrichir les descriptions des paramètres depuis l'OpenAPI
                if hasattr(route, 'parameters') and route.parameters:
                    for param in route.parameters:
                        if hasattr(param, 'name') and param.name:
                            transforms = {}
                            
                            # Ajouter une description si disponible
                            if hasattr(param, 'description') and param.description and param.description.strip():
                                transforms['description'] = param.description.strip()
                                param_count += 1
                            
                            # Note: L'attribut 'example' n'est pas disponible sur ParameterInfo
                            # Les exemples peuvent être ajoutés via d'autres moyens si nécessaire
                            
                            # Créer l'ArgTransform seulement s'il y a des transformations
                            if transforms:
                                arg_transforms[param.name] = ArgTransform(**transforms)
                                logger.debug(f"    - Enriching parameter '{param.name}': {list(transforms.keys())}")
                
                # === CRÉATION DE LA DESCRIPTION ENRICHIE ===
                tool_description = None
                if hasattr(route, 'description') and route.description and route.description.strip():
                    tool_description = route.description.strip()
                elif hasattr(route, 'summary') and route.summary and route.summary.strip():
                    # Fallback vers le summary si pas de description
                    tool_description = route.summary.strip()
                else:
                    # Description par défaut basée sur le nom de l'outil
                    tool_description = f"Execute the {new_name} operation on the Data Inclusion API"
                
                # === AJOUT DE TAGS POUR ORGANISATION ===
                tool_tags = {"data-inclusion", "api"}
                
                # Ajouter des tags spécifiques selon le type d'endpoint
                if "list_all" in new_name or "search" in new_name:
                    tool_tags.add("listing")
                if "get_" in new_name and "details" in new_name:
                    tool_tags.add("details")
                if "doc_" in new_name:
                    tool_tags.add("documentation")
                if any(endpoint in new_name for endpoint in ["structures", "services", "sources"]):
                    tool_tags.add("core-data")
                
                # === CRÉATION DU NOUVEL OUTIL TRANSFORMÉ ===
                transformed_tool = Tool.from_tool(
                    tool=original_tool,
                    name=new_name,
                    description=tool_description,
                    transform_args=arg_transforms if arg_transforms else None,
                    tags=tool_tags
                )
                
                # === AJOUT ET SUPPRESSION ===
                # Ajouter le nouvel outil au serveur
                mcp_server.add_tool(transformed_tool)
                
                # IMPORTANT: Supprimer l'outil original pour éviter les doublons
                # et la confusion pour le LLM
                try:
                    mcp_server.remove_tool(mangled_tool_name)
                    logger.debug(f"    - Removed original tool: '{mangled_tool_name}'")
                except Exception as remove_error:
                    # En cas d'échec de suppression, désactiver au moins l'outil
                    logger.debug(f"    - Could not remove '{mangled_tool_name}', disabling instead: {remove_error}")
                    original_tool.disable()
                
                # === LOGGING DE SUCCÈS ===
                successful_renames += 1
                enrichment_info = []
                
                if tool_description:
                    enrichment_info.append("description")
                if param_count > 0:
                    enrichment_info.append(f"{param_count} param descriptions")
                if tool_tags:
                    enrichment_info.append(f"{len(tool_tags)} tags")
                
                enrichment_msg = f" (enriched: {', '.join(enrichment_info)})" if enrichment_info else ""
                logger.info(f"  ✓ Transformed tool: '{original_name}' -> '{new_name}'{enrichment_msg}")
                
            except Exception as e:
                logger.error(f"  ✗ Failed to transform tool '{original_name}' -> '{new_name}': {e}")
                logger.debug(f"    Exception details: {type(e).__name__}: {str(e)}")
        
        # === RÉSUMÉ FINAL ===
        if successful_renames > 0:
            logger.info(f"✓ Tool transformation completed: {successful_renames}/{total_tools} tools successfully transformed")
        else:
            logger.warning(f"⚠️  No tools were successfully transformed out of {total_tools} attempted")
        
        # Vérifier que nous avons encore des outils après transformation
        final_tools = await mcp_server.get_tools()
        enabled_tools = [name for name, tool in final_tools.items() if tool.enabled]
        logger.info(f"📊 Final tool count: {len(enabled_tools)} enabled tools available")
        
        # === DEBUG: AFFICHER LES OPERATION_IDS DISPONIBLES ===
        # Afficher les operation_ids non mappés pour aider au debug
        logger.info("=== OpenAPI Route Analysis ===")
        available_ops = [route.operation_id for route in http_routes if hasattr(route, 'operation_id') and route.operation_id]
        unmapped_ops = [op_id for op_id in available_ops if op_id not in custom_mcp_tool_names]
        
        logger.info(f"Total OpenAPI routes: {len(available_ops)}")
        logger.info(f"Mapped routes: {len(custom_mcp_tool_names)}")
        logger.info(f"Unmapped routes: {len(unmapped_ops)}")
        
        if unmapped_ops:
            logger.info("⚠️  Unmapped operation_ids (should be added to custom_mcp_tool_names):")
            for op_id in sorted(unmapped_ops):
                logger.info(f"  - '{op_id}'")

        # === 11. INSPECTION DES COMPOSANTS MCP ===
        logger.info("Inspecting MCP components...")
        await inspect_mcp_components(mcp_server, logger)

        # === 12. LANCEMENT DU SERVEUR ===
        server_url = f"http://{settings.MCP_HOST}:{settings.MCP_PORT}{settings.MCP_API_PATH}"
        logger.info(f"Starting MCP server on {server_url}")
        logger.info("Press Ctrl+C to stop the server")
        
        await mcp_server.run_async(
            transport="http",
            host=settings.MCP_HOST,
            port=settings.MCP_PORT,
            path=settings.MCP_API_PATH
        )

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error("Please check your configuration and try again.")
        
    finally:
        # === 13. NETTOYAGE DES RESSOURCES ===
        if api_client:
            logger.info("Closing HTTP client...")
            await api_client.aclose()
            logger.info("HTTP client closed successfully")


if __name__ == "__main__":
    """
    Point d'entrée du script.
    Lance le serveur MCP avec gestion d'erreurs appropriée.
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Failed to start server: {e}")
        exit(1)