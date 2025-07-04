"""
Serveur web ASGI pour l'agent IA d'inclusion sociale utilisant le protocole A2A.

Ce module expose l'agent via une API web en utilisant la méthode standard agent.to_a2a()
de Pydantic AI avec FastA2A.
"""

import asyncio
import logging
import uvicorn
import httpx
from fasta2a import Skill
from fasta2a.broker import InMemoryBroker
from fasta2a.storage import InMemoryStorage
from pydantic_ai.mcp import MCPServerStreamableHTTP

from .agent import create_inclusion_agent
from .config import Settings

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def validate_mcp_url(url: str) -> bool:
    """Valide le format et l'accessibilité de l'URL MCP."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        # Vérification du format URL
        if not all([parsed.scheme, parsed.netloc]):
            logger.error(f"Invalid URL format: {url}")
            logger.error("URL must include scheme (http/https) and host")
            return False
            
        if parsed.scheme not in ['http', 'https']:
            logger.error(f"Unsupported URL scheme: {parsed.scheme}. Use http or https")
            return False
            
        logger.info(f"✓ URL format validation passed: {url}")
        return True
        
    except Exception as e:
        logger.error(f"URL validation failed: {type(e).__name__}: {e}")
        return False


async def create_agent_with_mcp():
    """
    Crée l'agent d'inclusion avec sa connexion MCP.
    
    Returns:
        Agent configuré et connecté au serveur MCP
    """
    # Charger la configuration
    settings = Settings()
    
    logger.info("=" * 60)
    logger.info("🚀 Starting DataInclusion Agent initialization...")
    logger.info(f"📡 Target MCP server: {settings.MCP_SERVER_URL}")
    logger.info(f"🔧 Agent port: {settings.AGENT_PORT}")
    logger.info("=" * 60)
    
    # Validation préalable de l'URL MCP
    if not await validate_mcp_url(settings.MCP_SERVER_URL):
        raise ValueError(f"Invalid MCP server URL: {settings.MCP_SERVER_URL}")
    
    # Instancier le client MCP
    try:
        logger.info("🔌 Creating MCP client connection...")
        mcp_server = MCPServerStreamableHTTP(url=settings.MCP_SERVER_URL)
        logger.info("✓ MCP client instance created successfully")
    except Exception as e:
        logger.error(f"✗ Failed to create MCP client: {type(e).__name__}: {e}")
        raise
    
    # Créer l'agent d'inclusion
    try:
        logger.info("🤖 Creating DataInclusion agent...")
        agent = create_inclusion_agent(mcp_server)
        logger.info("✓ Agent created successfully")
        return agent
    except Exception as e:
        logger.error(f"✗ Failed to create agent: {type(e).__name__}: {e}")
        raise


async def main():
    """
    Fonction principale qui configure et lance le serveur A2A.
    """
    # Charger la configuration
    settings = Settings()
    
    # Créer l'agent avec sa connexion MCP
    agent = await create_agent_with_mcp()
    
    # Extraire les métadonnées depuis l'agent pour l'application A2A
    # Utiliser le system_prompt de l'agent comme description
    description = (
        "Agent IA spécialisé dans l'inclusion sociale en France. "
        "Aide à trouver des informations sur les structures et services d'aide, "
        "les ressources disponibles sur le territoire français."
    )
    
    # Créer les compétences de l'agent
    skills = [
        Skill(
            id="datainclusion_chat",
            name="DataInclusion Chat",
            description="Recherche et fournit des informations sur les services d'inclusion sociale, les structures d'aide et les ressources disponibles en France",
            tags=["inclusion", "social", "france", "aide", "services"],
            examples=[
                "Trouve-moi des structures d'aide pour l'insertion professionnelle à Paris",
                "Quels sont les services disponibles pour l'aide au logement en région PACA ?",
                "Comment trouver de l'aide alimentaire près de chez moi ?"
            ],
            input_modes=["application/json"],
            output_modes=["application/json"]
        )
    ]
    
    # Instancier storage et broker
    storage = InMemoryStorage()
    broker = InMemoryBroker()
    
    # Configuration pour la logique de retry
    max_retries = settings.AGENT_MCP_CONNECTION_MAX_RETRIES
    base_delay = settings.AGENT_MCP_CONNECTION_BASE_DELAY
    backoff_multiplier = settings.AGENT_MCP_CONNECTION_BACKOFF_MULTIPLIER
    
    # Logique de retry pour la connexion au serveur MCP
    logger.info(f"🔄 Starting connection retry loop (max {max_retries} attempts)...")
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"⏳ Attempt {attempt}/{max_retries}: Connecting to MCP server at {settings.MCP_SERVER_URL}")
            
            # S'assurer que la connexion au serveur MCP est active
            async with agent.run_mcp_servers():
                logger.info("🎉 Successfully connected to MCP server!")
                logger.info("✅ Agent initialization completed successfully")
                logger.info("=" * 60)
                
                # Créer l'application A2A avec agent.to_a2a()
                app = agent.to_a2a(
                    storage=storage,
                    broker=broker,
                    name="DataInclusion Agent",
                    description=description,
                    url=f"http://localhost:{settings.AGENT_PORT}",
                    version="1.0.0",
                    skills=skills
                )
                
                # Créer et lancer le serveur Uvicorn de manière asynchrone
                logger.info(f"🚀 Starting Uvicorn server on port {settings.AGENT_PORT}...")
                config = uvicorn.Config(
                    app=app,
                    host="0.0.0.0",
                    port=settings.AGENT_PORT,
                    log_level="info"
                )
                server = uvicorn.Server(config)
                await server.serve()
                
                return  # Sortir de la fonction après succès
                
        except httpx.ConnectError as e:
            error_msg = f"🔌 Network connection failed (attempt {attempt})"
            logger.warning(f"{error_msg}: {e}")
            logger.warning(f"   Target URL: {settings.MCP_SERVER_URL}")
            
            if attempt == max_retries:
                logger.error("❌ CONNECTION FAILURE - MCP Server Unreachable")
                logger.error("=" * 60)
                logger.error("🔍 DIAGNOSIS STEPS:")
                logger.error("   1. Check if MCP server container is running:")
                logger.error("      docker-compose ps mcp_server")
                logger.error("   2. Check MCP server logs:")
                logger.error("      docker-compose logs mcp_server")
                logger.error("   3. Verify network connectivity:")
                logger.error(f"      docker exec agent_server curl -f {settings.MCP_SERVER_URL.replace('/mcp', '/health')}")
                logger.error("   4. Check Docker network:")
                logger.error("      docker network ls && docker network inspect mcp-data-inclusion_app-network")
                logger.error("=" * 60)
                raise ConnectionError(f"MCP server unreachable at {settings.MCP_SERVER_URL} after {max_retries} attempts")
            
        except httpx.TimeoutException as e:
            logger.warning(f"⏰ Request timeout (attempt {attempt}): {e}")
            logger.warning(f"   The MCP server is taking too long to respond")
            
            if attempt == max_retries:
                logger.error("❌ TIMEOUT FAILURE - MCP Server Too Slow")
                logger.error("🔍 POSSIBLE CAUSES:")
                logger.error("   • MCP server is overloaded or starting up")
                logger.error("   • Network latency issues")
                logger.error("   • Resource constraints (CPU/Memory)")
                logger.error("💡 TRY: Increase timeout or check server performance")
                raise asyncio.TimeoutError(f"MCP server timeout at {settings.MCP_SERVER_URL}")
                
        except ConnectionError as e:
            logger.warning(f"🚫 Connection error (attempt {attempt}): {e}")
            
            if attempt == max_retries:
                logger.error("❌ CONNECTION ERROR - Unable to establish connection")
                logger.error("🔍 CHECK: MCP server status and Docker network configuration")
                raise
                
        except asyncio.TimeoutError as e:
            logger.warning(f"⏰ Async timeout (attempt {attempt}): {e}")
            
            if attempt == max_retries:
                logger.error("❌ ASYNC TIMEOUT - Operation took too long")
                raise
                
        except Exception as e:
            logger.error(f"💥 Unexpected error (attempt {attempt}): {type(e).__name__}: {e}")
            logger.error(f"   Context: Connecting to {settings.MCP_SERVER_URL}")
            
            if attempt == max_retries:
                logger.error("❌ UNEXPECTED ERROR - Check application configuration")
                logger.error("🔍 DEBUG INFO:")
                logger.error(f"   • MCP URL: {settings.MCP_SERVER_URL}")
                logger.error(f"   • Agent Port: {settings.AGENT_PORT}")
                logger.error(f"   • Error Type: {type(e).__name__}")
                logger.error("💡 CHECK: Application logs and configuration files")
                raise
        
        # Calculer le délai avec backoff exponentiel (seulement si pas la dernière tentative)
        if attempt < max_retries:
            delay = base_delay * (backoff_multiplier ** (attempt - 1))
            logger.info(f"⏳ Retrying in {delay:.1f} seconds... ({max_retries - attempt} attempts remaining)")
            await asyncio.sleep(delay)


if __name__ == "__main__":
    asyncio.run(main()) 