"""
Serveur web ASGI pour l'agent IA d'inclusion sociale utilisant le protocole A2A.

Ce module expose l'agent via une API web en utilisant le protocole Agent-to-Agent
de Pydantic AI avec FastA2A.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
import httpx
import logfire
import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from fasta2a import FastA2A, Skill
from fasta2a.broker import InMemoryBroker
from fasta2a.storage import InMemoryStorage
from pydantic_ai.mcp import MCPServerStreamableHTTP

from .agent import create_inclusion_agent
from .config import Settings
from .persistence import RedisStorage, RedisBroker

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instances globales
agent = None
mcp_server = None


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


@asynccontextmanager
async def lifespan(app: FastA2A):
    """
    Gestionnaire de cycle de vie pour l'application FastA2A.
    
    Configure l'agent et la connexion MCP au démarrage et nettoie
    les ressources à l'arrêt.
    """
    global agent, mcp_server
    
    # Charger la configuration
    settings = Settings()
    
    # Configurer et instrumenter Logfire pour l'observabilité
    logfire.configure()
    logfire.instrument_pydantic_ai()
    
    logger.info("=" * 60)
    logger.info("🚀 Starting DataInclusion Agent initialization...")
    logger.info(f"📡 Target MCP server: {settings.MCP_SERVER_URL}")
    logger.info(f"🔧 Agent port: {settings.AGENT_PORT}")
    logger.info(f"🗄️ Redis server: {settings.REDIS_URL}")
    logger.info("=" * 60)
    
    # Validation préalable de l'URL MCP
    if not await validate_mcp_url(settings.MCP_SERVER_URL):
        raise ValueError(f"Invalid MCP server URL: {settings.MCP_SERVER_URL}")
    
    # Initialiser/Vérifier les composants Redis
    try:
        logger.info("🔌 Verifying Redis client connection...")
        
        # Utiliser le client Redis global déjà créé
        global _redis_client
        if _redis_client is None:
            logger.warning("Redis client not initialized, creating new one...")
            redis_client, _, _ = create_redis_components(settings)
        else:
            redis_client = _redis_client
        
        # Tester la connexion Redis
        await redis_client.ping()
        logger.info("✓ Redis client connected successfully")
        
        # Stocker le client Redis dans l'état de l'application
        app.state.redis_client = redis_client
        
    except Exception as e:
        logger.error(f"✗ Failed to connect to Redis: {type(e).__name__}: {e}")
        logger.error("🔍 REDIS TROUBLESHOOTING:")
        logger.error(f"   • Redis URL: {settings.REDIS_URL}")
        logger.error("   • Check if Redis container is running: docker-compose ps redis")
        logger.error("   • Check Redis logs: docker-compose logs redis")
        logger.error("   • Verify Redis health: docker exec redis redis-cli ping")
        raise
    
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
    except Exception as e:
        logger.error(f"✗ Failed to create agent: {type(e).__name__}: {e}")
        raise
    
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
                
                # Stocker l'agent dans l'état de l'application
                app.state.agent = agent
                yield  # Passer la main à l'application
                
                # Nettoyage des ressources après l'arrêt de l'application
                logger.info("🧹 Cleaning up resources...")
                try:
                    if hasattr(app.state, 'redis_client'):
                        await app.state.redis_client.aclose()
                        logger.info("✓ Redis client connection closed")
                except Exception as e:
                    logger.error(f"Error closing Redis client: {e}")
                
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


# Variables globales pour les composants partagés
_redis_client = None
_redis_storage = None
_redis_broker = None


def create_redis_components(settings: Settings):
    """Créer les composants Redis configurés pour la production."""
    global _redis_client, _redis_storage, _redis_broker
    
    # Configuration Redis avec pool de connexions optimisé
    redis_client = redis.from_url(
        settings.REDIS_URL,
        retry_on_error=[RedisConnectionError, RedisTimeoutError],
        retry=Retry(ExponentialBackoff(), 3),
        health_check_interval=30,  # Vérification périodique des connexions
        socket_connect_timeout=5,   # Timeout de connexion
        socket_timeout=5,           # Timeout de lecture/écriture
        max_connections=20,         # Pool de connexions
    )
    
    # Créer les composants Redis robustes
    redis_storage = RedisStorage(
        redis_client=redis_client,
        task_ttl=7 * 24 * 3600,    # 7 jours
        max_retries=3
    )
    
    redis_broker = RedisBroker(
        redis_client=redis_client,
        channel_name="fasta2a:tasks",
        max_retries=3,
        reconnect_interval=5
    )
    
    _redis_client = redis_client
    _redis_storage = redis_storage
    _redis_broker = redis_broker
    
    return redis_client, redis_storage, redis_broker


def create_app() -> FastA2A:
    """Créer l'application FastA2A avec architecture Redis robuste."""
    # Charger la configuration
    settings = Settings()
    
    # Créer les composants Redis partagés
    redis_client, redis_storage, redis_broker = create_redis_components(settings)
    
    return FastA2A(
        # Configuration du stockage et du broker Redis
        storage=redis_storage,
        broker=redis_broker,
        
        # Métadonnées de l'agent
        name="DataInclusion Agent",
        description="Agent IA spécialisé dans l'inclusion sociale en France. Aide à trouver des informations sur les structures et services d'aide, les ressources disponibles sur le territoire français.",
        url="http://localhost:8001",
        version="1.0.0",
        
        # Compétences de l'agent
        skills=[
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
        ],
        
        # Gestionnaire de cycle de vie
        lifespan=lifespan
    )


# Créer l'instance de l'application
app = create_app()


if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(
        "src.agent.server:app",
        host="0.0.0.0",
        port=settings.AGENT_PORT,
        reload=True
    ) 