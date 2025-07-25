"""
Factory class for constructing and configuring the MCP server.
"""

import json
import logging
from typing import Dict, Any

from fastmcp import FastMCP
from fastmcp.server.openapi import RouteMap, MCPType
from starlette.requests import Request
from starlette.responses import PlainTextResponse
import httpx  # Add this import for httpx.AsyncClient

from ..core.config import MCPServiceConfig
from .openapi_loader import OpenAPILoader
from .tool_transformer import ToolTransformer
from .auth import create_auth_handler  # Import the new auth handler


class MCPFactory:
    """
    Factory class for constructing and configuring the MCP server.

    This class orchestrates the construction of the MCP server using
    specialized components (OpenAPILoader, ToolTransformer, etc.).
    """

    def __init__(self, config: MCPServiceConfig, logger: logging.Logger):
        """
        Initializes the factory with the service configuration and logger.

        Args:
            config: The MCP service configuration.
            logger: Logger instance for logging messages.
        """
        self.config = config
        self.logger = logger
        self.api_client = None
        self.openapi_spec = None
        self.http_routes = None
        self.base_url = None
        self.op_id_to_mangled_name = {}
        self.tool_mappings = {}

    async def _load_openapi_spec(self) -> None:
        """
        Loads and parses the OpenAPI specification.

        This method uses OpenAPILoader to load the OpenAPI specification
        and extract HTTP routes.

        Raises:
            Exception: If loading the specification fails.
        """
        self.logger.info("Loading OpenAPI specification...")
        openapi_loader = OpenAPILoader(self.logger)
        self.openapi_spec, self.http_routes = await openapi_loader.load(
            self.config.openapi_path_or_url  # Use openapi_path_or_url
        )

    def _determine_base_url(self) -> None:
        """
        Determines the base URL from the OpenAPI specification.

        This method analyzes the 'servers' section of the OpenAPI specification
        to determine the server's base URL.
        """
        if not self.openapi_spec:
            raise ValueError("OpenAPI specification not loaded")

        servers = self.openapi_spec.get("servers", [])
        if (
            servers
            and isinstance(servers, list)
            and len(servers) > 0
            and "url" in servers[0]
        ):
            self.base_url = servers[0]["url"]
            self.logger.info(f"Using base URL from OpenAPI spec: {self.base_url}")
        else:
            self.base_url = "http://localhost:8000"  # Default if not found in spec
            self.logger.warning("No servers section found in OpenAPI spec.")
            self.logger.warning(f"Using default base URL: {self.base_url}")

    def _create_api_client(self) -> None:
        """
        Creates the authenticated HTTP API client.

        This method creates an HTTP client configured with the base URL
        and appropriate authentication parameters.
        """
        if not self.base_url:
            raise ValueError("Base URL not determined")

        self.logger.info("Creating HTTP client with new authentication handler...")
        auth_handler = create_auth_handler(self.config.auth, self.logger)

        headers = {
            "User-Agent": "DataInclusion-MCP-Server/1.0",
            "Accept": "application/json",
        }

        self.api_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=30.0,
            auth=auth_handler,  # Pass the auth handler
        )
        self.logger.info("HTTP client created successfully with authentication.")

    def _load_tool_mappings(self) -> Dict[str, Any]:
        """
        Loads custom tool mappings from a specified JSON file.

        Returns:
            Dict[str, Any]: A dictionary of custom tool mappings.
        """
        if not self.config.tool_mappings_file:
            self.logger.info(
                "No custom tool mappings file specified. Using empty mappings."
            )
            return {}

        try:
            with open(self.config.tool_mappings_file, "r", encoding="utf-8") as f:
                mappings = json.load(f)
            self.logger.info(
                f"Loaded custom tool mappings from {self.config.tool_mappings_file}"
            )
            return mappings
        except FileNotFoundError:
            self.logger.warning(
                f"Custom tool mappings file not found: {self.config.tool_mappings_file}. "
                "Using empty mappings."
            )
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(
                f"Error decoding JSON from tool mappings file {self.config.tool_mappings_file}: {e}. "
                "Using empty mappings."
            )
            return {}

    def _create_mcp_server(self) -> FastMCP:
        """
        Creates and configures the MCP server.

        This method creates the FastMCP instance with the OpenAPI specification,
        the HTTP client, and authentication configuration.

        Args:
            auth_provider: Authentication provider or None.

        Returns:
            FastMCP: Configured instance of the MCP server.

        Raises:
            Exception: If server creation fails.
        """
        if not self.openapi_spec:
            raise ValueError("OpenAPI specification not loaded")
        if not self.http_routes:
            raise ValueError("HTTP routes not loaded")
        if not self.api_client:
            raise ValueError("API client not created")

        self.logger.info(f"Creating FastMCP server '{self.config.name}'...")

        # Configuration des routes MCP
        route_maps = []
        if self.config.name == "datainclusion":
            allowed_op_ids = set(self.tool_mappings.keys())
            for route in self.http_routes:
                if route.operation_id in allowed_op_ids:
                    route_maps.append(
                        RouteMap(
                            methods=[route.method],
                            pattern=f"^{route.path}$",
                            mcp_type=MCPType.TOOL,
                        )
                    )
            route_maps.append(RouteMap(mcp_type=MCPType.EXCLUDE))

        # Création du transformer temporaire pour le callback
        temp_transformer = ToolTransformer(
            mcp_server=None,  # type: ignore # Sera défini après création du serveur
            http_routes=self.http_routes,
            custom_tool_names=self.tool_mappings,  # Use loaded mappings
            op_id_map=self.op_id_to_mangled_name,
            logger=self.logger,
        )

        # Création du serveur MCP
        mcp_server = FastMCP.from_openapi(
            openapi_spec=self.openapi_spec,
            client=self.api_client,
            name=self.config.name,
            route_maps=route_maps,  # Pass the dynamically created route_maps
            auth=None,
            mcp_component_fn=temp_transformer.discover_and_customize,
        )

        # Ajout de l'endpoint de santé
        @mcp_server.custom_route("/health", methods=["GET"])
        async def health_check(_request: Request) -> PlainTextResponse:
            """A simple health check endpoint."""
            return PlainTextResponse("OK", status_code=200)

        self.logger.info(f"FastMCP server '{mcp_server.name}' created successfully!")
        self.logger.info("   - Custom GET-to-Tool mapping applied")
        self.logger.info("   - Health check endpoint (/health) added successfully")

        return mcp_server

    async def _transform_tools(self, mcp_server: FastMCP) -> None:
        """
        Transforms the MCP tools.

        This method uses ToolTransformer to apply custom transformations
        to the generated MCP tools.

        Args:
            mcp_server: Instance of the MCP server.

        Raises:
            Exception: If tool transformation fails.
        """
        if not self.http_routes:
            raise ValueError("HTTP routes not loaded")

        self.logger.info("Transforming tools...")
        tool_transformer = ToolTransformer(
            mcp_server=mcp_server,
            http_routes=self.http_routes,
            custom_tool_names=self.tool_mappings,  # Use loaded mappings
            op_id_map=self.op_id_to_mangled_name,
            logger=self.logger,
        )
        await tool_transformer.transform_tools()

    async def build(self) -> FastMCP:
        """
        Orchestrates the complete construction of the MCP server.

        This method uses specialized components to build the MCP server
        in a modular and organized manner.

        Returns:
            FastMCP: Fully configured instance of the MCP server.

        Raises:
            Exception: If any build step fails.
        """
        try:
            # 1. Load custom tool mappings
            self.tool_mappings = self._load_tool_mappings()

            # 2. Load and parse the OpenAPI specification
            await self._load_openapi_spec()

            # 3. Determine the base URL
            self._determine_base_url()

            # 4. Create the authenticated API client
            self._create_api_client()

            # 5. Configure authentication
            # auth_provider = self._configure_auth()

            # 6. Create the MCP server
            mcp_server = self._create_mcp_server()

            # 7. Transform tools
            await self._transform_tools(mcp_server)

            return mcp_server

        except Exception as e:
            self.logger.error(f"Failed to build MCP server: {e}")
            if self.api_client:
                await self.api_client.aclose()
            raise

    async def cleanup(self) -> None:
        """
        Cleans up resources used by the factory.
        """
        if self.api_client:
            self.logger.info("Closing HTTP client...")
            await self.api_client.aclose()
            self.logger.info("HTTP client closed successfully")
