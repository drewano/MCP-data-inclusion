"""
DataInclusion MCP Server

Ce serveur MCP expose l'API data.inclusion.beta.gouv.fr via le protocole Model Context Protocol.
Il transforme automatiquement les endpoints OpenAPI en outils MCP.
"""

import asyncio
import logging
from fastmcp import FastMCP
from fastmcp.server.openapi import RouteMap, MCPType
from fastmcp.server.auth import BearerAuthProvider
from fastmcp.server.auth.providers.bearer import RSAKeyPair
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from ..core.config import settings
from .utils import inspect_mcp_components, create_api_client
from ..core.logging import setup_logging
from .openapi_loader import OpenAPILoader
from .tool_transformer import ToolTransformer
from .tool_mapping import CUSTOM_MCP_TOOL_NAMES


class MCPBuilder:
    """
    Builder class pour construire et configurer le serveur MCP.

    Cette classe orchestre la construction du serveur MCP en utilisant
    les composants spécialisés (OpenAPILoader, ToolTransformer, etc.).
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize the MCPBuilder with a logger instance.
        
        The logger is used for recording informational, warning, and error messages throughout the server build process.
        """
        self.logger = logger
        self.api_client = None

    def _configure_auth(self) -> BearerAuthProvider | None:
        """
        Configures Bearer token authentication for the MCP server.
        
        If a secret key is provided in the configuration, sets up a BearerAuthProvider using either an existing PEM-encoded RSA private key or a newly generated RSA key pair. Logs a test token for development if a new key pair is generated. Returns the authentication provider if successful, or None if no key is set or configuration fails.
        """
        self.logger.info("Configuring server authentication...")

        # Lecture de la clé secrète depuis la configuration
        secret_key = settings.mcp.MCP_SERVER_SECRET_KEY

        if secret_key and secret_key.strip():
            self.logger.info(
                "Secret key found - configuring Bearer Token authentication..."
            )
            try:
                # Si la clé ressemble à une clé RSA privée PEM, l'utiliser directement
                if (
                    secret_key.strip().startswith("-----BEGIN")
                    and "PRIVATE KEY" in secret_key
                ):
                    # Utiliser la clé privée pour créer une paire de clés
                    from cryptography.hazmat.primitives import serialization

                    private_key = serialization.load_pem_private_key(
                        secret_key.encode(), password=None
                    )
                    public_key_pem = (
                        private_key.public_key()
                        .public_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PublicFormat.SubjectPublicKeyInfo,
                        )
                        .decode()
                    )

                    auth_provider = BearerAuthProvider(
                        public_key=public_key_pem, audience="datainclusion-mcp-client"
                    )
                else:
                    # Utiliser la clé comme seed pour générer une paire de clés déterministe
                    # Pour des raisons de simplicité, on génère une nouvelle paire de clés
                    key_pair = RSAKeyPair.generate()

                    auth_provider = BearerAuthProvider(
                        public_key=key_pair.public_key,
                        audience="datainclusion-mcp-client",
                    )

                    # Log du token de test (UNIQUEMENT pour le développement)
                    test_token = key_pair.create_token(
                        audience="datainclusion-mcp-client",
                        subject="test-user",
                        expires_in_seconds=3600,
                    )
                    self.logger.info(
                        f"🔑 Test Bearer Token (for development): {test_token}"
                    )

                self.logger.info(
                    "✓ Bearer Token authentication configured successfully"
                )
                self.logger.info("   - Audience: datainclusion-mcp-client")
                self.logger.info(
                    "   - Server will require valid Bearer tokens for access"
                )
                return auth_provider

            except Exception as e:
                self.logger.error(f"Failed to configure authentication: {e}")
                self.logger.warning("Continuing without authentication...")
                return None
        else:
            self.logger.warning(
                "MCP_SERVER_SECRET_KEY not set - server will run WITHOUT authentication"
            )
            self.logger.warning(
                "⚠️  All clients will have unrestricted access to the server"
            )
            return None

    async def build(self) -> FastMCP:
        """
        Builds and configures the MCP server by loading the OpenAPI specification, setting up authentication, transforming HTTP routes into MCP tools, and adding a health check endpoint.
        
        Returns:
            FastMCP: The fully configured MCP server instance.
        
        Raises:
            Exception: If any step in the server construction process fails.
        """
        try:
            # 1. Chargement et parsing de la spécification OpenAPI
            self.logger.info("Loading OpenAPI specification...")
            openapi_loader = OpenAPILoader(self.logger)
            openapi_spec, http_routes = await openapi_loader.load()

            # 2. Création du client API authentifié
            self.logger.info("Creating HTTP client...")
            servers = openapi_spec.get("servers", [])
            if (
                servers
                and isinstance(servers, list)
                and len(servers) > 0
                and "url" in servers[0]
            ):
                base_url = servers[0]["url"]
                self.logger.info(f"Using base URL from OpenAPI spec: {base_url}")
            else:
                base_url = "http://localhost:8000"
                self.logger.warning("No servers section found in OpenAPI spec.")
                self.logger.warning(f"Using default base URL: {base_url}")

            self.api_client = create_api_client(
                base_url, self.logger, settings.mcp.DATA_INCLUSION_API_KEY
            )

            # 3. Configuration de l'authentification
            auth_provider = self._configure_auth()

            # 4. Création du serveur MCP
            self.logger.info(
                f"Creating FastMCP server '{settings.mcp.MCP_SERVER_NAME}'..."
            )

            # Configuration des routes MCP
            custom_route_maps = [
                RouteMap(methods=["GET"], pattern=r".*", mcp_type=MCPType.TOOL),
            ]

            # Dictionnaire pour stocker le mapping operation_id -> nom d'outil
            op_id_to_mangled_name = {}

            # Création du transformer temporaire pour le callback
            temp_transformer = ToolTransformer(
                mcp_server=None,  # type: ignore # Sera défini après création du serveur
                http_routes=http_routes,
                custom_tool_names=CUSTOM_MCP_TOOL_NAMES,
                op_id_map=op_id_to_mangled_name,
                logger=self.logger,
            )

            # Création du serveur MCP
            mcp_server = FastMCP.from_openapi(
                openapi_spec=openapi_spec,
                client=self.api_client,
                name=settings.mcp.MCP_SERVER_NAME,
                route_maps=custom_route_maps,
                auth=auth_provider,
                mcp_component_fn=lambda route,
                component: temp_transformer.discover_and_customize(route, component),
            )

            # Ajout de l'endpoint de santé
            @mcp_server.custom_route("/health", methods=["GET"])
            async def health_check(request: Request) -> PlainTextResponse:
                """
                Handles health check requests and returns a plain text "OK" response with HTTP 200 status.
                """
                return PlainTextResponse("OK", status_code=200)

            self.logger.info(
                f"FastMCP server '{mcp_server.name}' created successfully!"
            )
            self.logger.info("   - Custom GET-to-Tool mapping applied")
            self.logger.info("   - Health check endpoint (/health) added successfully")

            # 5. Transformation des outils
            self.logger.info("Transforming tools...")
            tool_transformer = ToolTransformer(
                mcp_server=mcp_server,
                http_routes=http_routes,
                custom_tool_names=CUSTOM_MCP_TOOL_NAMES,
                op_id_map=op_id_to_mangled_name,
                logger=self.logger,
            )
            await tool_transformer.transform_tools()

            # 6. Inspection des composants (pour debug)
            await inspect_mcp_components(mcp_server, self.logger)

            return mcp_server

        except Exception as e:
            self.logger.error(f"Failed to build MCP server: {e}")
            if self.api_client:
                await self.api_client.aclose()
            raise

    async def cleanup(self) -> None:
        """
        Release resources used by the builder, closing the HTTP client if it was created.
        """
        if self.api_client:
            self.logger.info("Closing HTTP client...")
            await self.api_client.aclose()
            self.logger.info("HTTP client closed successfully")


async def main():
    """
    Asynchronously configures, builds, and runs the MCP server, handling startup, shutdown, and resource cleanup.
    
    Initializes logging, constructs the MCP server using MCPBuilder, and starts it with the configured host, port, and API path. Handles graceful shutdown on keyboard interrupt and logs unexpected errors. Ensures proper cleanup of resources regardless of execution outcome.
    """

    # === 1. CONFIGURATION DU LOGGING ===
    logger = setup_logging(name="datainclusion.mcp")

    builder = None

    try:
        # === 2. CRÉATION ET CONSTRUCTION DU SERVEUR MCP ===
        logger.info("Initializing MCP server builder...")
        builder = MCPBuilder(logger)

        logger.info("Building MCP server...")
        mcp_server = await builder.build()

        # === 3. LANCEMENT DU SERVEUR ===
        server_url = f"http://{settings.mcp.MCP_HOST}:{settings.mcp.MCP_PORT}{settings.mcp.MCP_API_PATH}"
        logger.info(f"Starting MCP server on {server_url}")
        logger.info("Press Ctrl+C to stop the server")

        await mcp_server.run_async(
            transport="http",
            host=settings.mcp.MCP_HOST,
            port=settings.mcp.MCP_PORT,
            path=settings.mcp.MCP_API_PATH,
        )

    except KeyboardInterrupt:
        logger.info("Server stopped by user")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error("Please check your configuration and try again.")

    finally:
        # === 4. NETTOYAGE DES RESSOURCES ===
        if builder:
            await builder.cleanup()


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
