"""
Module de chargement et pré-traitement de la spécification OpenAPI.

Ce module contient la classe OpenAPILoader qui centralise la logique de chargement
et de pré-traitement des spécifications OpenAPI pour le serveur MCP.
"""

import json
import logging
from typing import List, Dict, Tuple
import httpx
from fastmcp.utilities.openapi import parse_openapi_to_http_routes, HTTPRoute

from ..core.config import settings


class OpenAPILoader:
    """
    Classe responsable du chargement et du pré-traitement de la spécification OpenAPI.

    Cette classe encapsule toute la logique de :
    - Chargement de la spécification OpenAPI depuis une URL
    - Parsing des routes HTTP
    - Application des limites de pagination
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize the OpenAPILoader with a logger for recording messages.
        """
        self.logger = logger

    async def load(self) -> Tuple[Dict, List[HTTPRoute]]:
        """
        Asynchronously loads and preprocesses the OpenAPI specification from a configured URL.
        
        Fetches the OpenAPI JSON specification, parses it into HTTP routes, and applies pagination limits to specific endpoints. Returns the modified specification and the list of parsed HTTP routes.
        
        Returns:
            Tuple[Dict, List[HTTPRoute]]: The modified OpenAPI specification and the list of parsed HTTP routes.
        
        Raises:
            httpx.RequestError: If the OpenAPI specification cannot be fetched.
            json.JSONDecodeError: If the response is not valid JSON.
        """
        self.logger.info(
            f"Loading OpenAPI specification from URL: '{settings.mcp.OPENAPI_URL}'..."
        )

        try:
            # === CHARGEMENT DE LA SPÉCIFICATION OPENAPI ===
            async with httpx.AsyncClient() as client:
                response = await client.get(settings.mcp.OPENAPI_URL)
                response.raise_for_status()  # Lève une exception si le statut n'est pas 2xx
                openapi_spec = response.json()

            api_title = openapi_spec.get("info", {}).get("title", "Unknown API")
            self.logger.info(f"Successfully loaded OpenAPI spec: '{api_title}'")

            # === PRÉ-PARSING DE LA SPÉCIFICATION OPENAPI ===
            self.logger.info("Parsing OpenAPI specification to HTTP routes...")
            http_routes = parse_openapi_to_http_routes(openapi_spec)
            self.logger.info(
                f"Successfully parsed {len(http_routes)} HTTP routes from OpenAPI specification"
            )

            # === MODIFICATION DES LIMITES DE PAGINATION ===
            # Limite la taille des pages pour les outils de listing à 25 éléments maximum
            # Cela s'applique aux outils: list_all_structures, list_all_services, search_services
            self.logger.info("Applying pagination limits to data-listing endpoints...")
            openapi_spec = self._limit_page_size(openapi_spec, max_size=25)

            return openapi_spec, http_routes

        except httpx.RequestError as e:
            self.logger.error(
                f"Failed to fetch OpenAPI specification from '{settings.mcp.OPENAPI_URL}'."
            )
            self.logger.error(f"Details: {e}")
            raise

        except json.JSONDecodeError as e:
            self.logger.error(
                f"Invalid JSON in the response from '{settings.mcp.OPENAPI_URL}'."
            )
            self.logger.error(f"Details: {e}")
            raise

    def _limit_page_size(self, spec: dict, max_size: int = 25) -> dict:
        """
        Modify the OpenAPI specification to enforce a maximum page size for specific endpoints.
        
        For each targeted GET endpoint, sets the 'size' query parameter's maximum and default values to `max_size` to prevent excessively large paginated responses.
        
        Parameters:
            spec (dict): The OpenAPI specification to modify.
            max_size (int): The maximum allowed value for the 'size' parameter (default is 25).
        
        Returns:
            dict: The modified OpenAPI specification with page size limits applied.
        """
        paths_to_modify = [
            "/api/v0/structures",
            "/api/v0/services",
            "/api/v0/search/services",
        ]

        self.logger.info(f"Applying page size limit (max_size={max_size}) to spec...")

        for path in paths_to_modify:
            if path in spec["paths"] and "get" in spec["paths"][path]:
                params = spec["paths"][path]["get"].get("parameters", [])
                for param in params:
                    if param.get("name") == "size":
                        param["schema"]["maximum"] = max_size
                        param["schema"]["default"] = max_size
                        self.logger.info(
                            f"  - Limited 'size' parameter for endpoint: GET {path}"
                        )

        return spec
