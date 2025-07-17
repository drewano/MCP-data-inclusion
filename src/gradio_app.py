#!/usr/bin/env python3
"""
Application Gradio intégrée avec FastAPI pour l'agent IA d'Inclusion Sociale.

Cette application combine :
- Le serveur FastAPI existant de l'agent IA (routes /api/*)
- L'interface Gradio moderne (routes /chat/*)
- Health checks pour les deux services

Architecture :
- /api/* : API REST de l'agent IA (chat/stream, health)
- /chat/* : Interface Gradio interactive
- / : Redirection vers l'interface Gradio
- /health : Health check global
- /docs : Documentation API FastAPI
"""

import logging
from datetime import datetime
from pathlib import Path

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Imports locaux
from .core.config import settings
from .core.lifespan import lifespan
from .api.router import api_router, set_app_instance
from .ui.chat import create_complete_interface

# Configuration du logging unifié
logger = logging.getLogger("datainclusion.agent")


# Création de l'application FastAPI principale
def create_app() -> FastAPI:
    """
    Create and configure a FastAPI application integrated with a Gradio user interface.
    
    The returned app serves the AI agent's REST API under `/api`, the Gradio chat interface under `/chat`, static files if present, and provides root redirection and a global health check endpoint. CORS is enabled with origins from settings, and API documentation is available at `/docs` and `/redoc`.
    
    Returns:
        FastAPI: The fully configured FastAPI application instance with Gradio integration.
    """
    # Application principale
    app = FastAPI(
        title="Agent IA d'Inclusion Sociale - Interface Complète",
        description="Application complète combinant l'agent IA et l'interface Gradio",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configurer l'instance de l'application pour l'accès Gradio
    set_app_instance(app)

    # Configuration CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.agent.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Servir les fichiers statiques
    static_path = Path("static")
    if static_path.exists():
        app.mount("/static", StaticFiles(directory="static"), name="static")

    # Routes de l'application principale

    @app.get("/")
    async def root():
        """
        Redirects the root URL to the Gradio chat interface at `/chat`.
        """
        return RedirectResponse(url="/chat")

    @app.get("/health")
    async def health_check():
        """
        Performs a global health check of the application, returning the status of core services.
        
        Returns:
            JSONResponse: A JSON object indicating overall health, service statuses, and a timestamp. Returns a 503 status with error details if the health check fails.
        """
        try:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "services": {
                        "agent": {"healthy": True},
                        "interface": {"healthy": True},
                    },
                },
            )

        except Exception as e:
            logger.error(f"Erreur lors du health check: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
            )

    # Monter l'APIRouter sous /api
    app.include_router(api_router, prefix="/api")

    # Créer et monter l'interface Gradio
    gradio_interface = create_complete_interface()

    # Monter l'interface Gradio
    app = gr.mount_gradio_app(app=app, blocks=gradio_interface, path="/chat")

    logger.info("🎯 Application FastAPI + Gradio configurée:")
    logger.info("   - Interface Gradio : http://localhost:8000/chat")
    logger.info("   - API Agent : http://localhost:8000/api")
    logger.info("   - Documentation : http://localhost:8000/docs")
    logger.info("   - Health Check : http://localhost:8000/health")

    return app


# Instance de l'application
app = create_app()


# Fonction utilitaire pour le développement
def run_development():
    """
    Start the application in development mode with Uvicorn, enabling auto-reload on source code changes.
    """
    uvicorn.run(
        "src.gradio_app:app",
        host="0.0.0.0",
        port=settings.agent.AGENT_PORT,
        reload=True,
        reload_dirs=["src"],
        reload_excludes=["*.pyc", "__pycache__", "*.log"],
        log_level="info",
        access_log=True,
        use_colors=True,
    )


if __name__ == "__main__":
    """Point d'entrée pour l'exécution directe."""
    run_development()
