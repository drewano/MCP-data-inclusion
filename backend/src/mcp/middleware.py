"""
Middleware personnalisés pour le serveur MCP DataInclusion.
"""

import time
import logging
import httpx
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError, ResourceError
from mcp import McpError
from mcp.types import ErrorData


class ErrorHandlingMiddleware(Middleware):
    """
    Middleware pour capturer les exceptions et les transformer en erreurs MCP standardisées.
    
    Ce middleware intercepte toutes les exceptions non gérées et les transforme en
    erreurs MCP standardisées avec des codes d'erreur appropriés pour le client.
    
    Gestion spécialisée pour :
    - McpError : Re-levées sans modification (déjà standardisées)
    - ToolError/ResourceError : Messages spécifiques préservés 
    - HTTPStatusError : Extraction des détails d'erreur API
    - Autres exceptions : Préservation du message original quand informatif
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialise le middleware de gestion d'erreurs.
        
        Args:
            logger: Instance du logger pour enregistrer les erreurs
        """
        self.logger = logger
    
    async def on_request(self, context: MiddlewareContext, call_next):
        """
        Intercepte les requêtes MCP pour capturer et standardiser les erreurs.
        
        Args:
            context: Contexte de la requête MCP contenant les métadonnées
            call_next: Fonction pour continuer la chaîne de middleware
            
        Returns:
            Le résultat de la requête après traitement
            
        Raises:
            McpError: Exception MCP standardisée avec ErrorData approprié
        """
        try:
            # Traiter la requête normalement
            return await call_next(context)
            
        except McpError:
            # Re-lever les erreurs MCP déjà standardisées sans modification
            raise
            
        except (ToolError, ResourceError) as e:
            # Logger l'erreur spécifique des outils/ressources MCP
            self.logger.error(
                f"MCP tool/resource error in {context.method}: {type(e).__name__}: {e}",
                exc_info=True
            )
            
            # Créer une ErrorData avec le message spécifique de l'outil
            # Code -32603 : Erreur interne (selon la spec JSON-RPC)
            error_data = ErrorData(
                code=-32603,
                message=str(e)  # Préserver le message spécifique de l'outil
            )
            
            # Lever une McpError standardisée pour le client
            raise McpError(error_data)
            
        except httpx.HTTPStatusError as e:
            # Logger l'erreur HTTP de manière détaillée
            self.logger.error(
                f"HTTP status error in {context.method}: {e.response.status_code} {e.response.reason_phrase}",
                exc_info=True
            )
            
            # Essayer de parser la réponse JSON pour extraire les détails
            error_details = None
            try:
                error_details = e.response.json()
            except Exception:
                # Si on ne peut pas parser le JSON, utiliser le texte brut
                try:
                    error_details = {"message": e.response.text}
                except Exception:
                    error_details = {"message": "Unable to parse error response"}
            
            # Construire un message d'erreur clair
            status_code = e.response.status_code
            reason = e.response.reason_phrase or "Unknown Error"
            
            if isinstance(error_details, dict):
                # Extraire le message d'erreur principal
                error_field = error_details.get("error")
                if isinstance(error_field, dict):
                    api_message = error_field.get("message", "No error message available")
                else:
                    api_message = (
                        error_details.get("message") 
                        or error_details.get("detail")
                        or str(error_details.get("error", ""))
                        or "No error details available"
                    )
                
                detailed_message = f"API Error {status_code} ({reason}): {api_message}"
                
                # Ajouter des détails supplémentaires si disponibles
                if "error_code" in error_details:
                    detailed_message += f" [Code: {error_details['error_code']}]"
                elif isinstance(error_field, dict) and "code" in error_field:
                    detailed_message += f" [Code: {error_field.get('code')}]"
                    
            else:
                detailed_message = f"API Error {status_code} ({reason}): {str(error_details)}"
            
            # Créer une ErrorData avec le code Invalid Params (-32602)
            error_data = ErrorData(
                code=-32602,
                message=detailed_message
            )
            
            # Lever une McpError standardisée pour le client
            raise McpError(error_data)
            
        except Exception as e:
            # Logger l'erreur de manière détaillée
            self.logger.error(
                f"Unhandled exception in {context.method}: {type(e).__name__}: {e}",
                exc_info=True  # Inclut la stack trace complète
            )
            
            # Préserver le message d'erreur original s'il est informatif
            original_message = str(e).strip()
            if original_message and len(original_message) < 500:  # Éviter les messages trop longs
                detailed_message = f"{type(e).__name__}: {original_message}"
            else:
                detailed_message = f"Internal server error: {type(e).__name__}"
            
            # Transformer l'exception en erreur MCP standardisée
            # Code -32000 : Erreur interne du serveur (selon la spec JSON-RPC)
            error_data = ErrorData(
                code=-32000,
                message=detailed_message
            )
            
            # Lever une McpError standardisée pour le client
            raise McpError(error_data)


class TimingMiddleware(Middleware):
    """
    Middleware pour mesurer et journaliser le temps d'exécution des requêtes MCP.
    
    Ce middleware intercepte toutes les requêtes MCP, mesure leur temps d'exécution
    et enregistre les métriques de performance via le système de logging.
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialise le middleware de timing.
        
        Args:
            logger: Instance du logger pour enregistrer les métriques de performance
        """
        self.logger = logger
    
    async def on_request(self, context: MiddlewareContext, call_next):
        """
        Intercepte les requêtes MCP pour mesurer leur temps d'exécution.
        
        Args:
            context: Contexte de la requête MCP contenant les métadonnées
            call_next: Fonction pour continuer la chaîne de middleware
            
        Returns:
            Le résultat de la requête après traitement
        """
        # Enregistrer le temps de début
        start_time = time.perf_counter()
        
        try:
            # Traiter la requête
            result = await call_next(context)
            
            # Calculer la durée en millisecondes
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Journaliser le succès de la requête
            self.logger.info(
                f"Request {context.method} completed in {duration_ms:.2f}ms"
            )
            
            return result
            
        except Exception as e:
            # Calculer la durée même en cas d'erreur
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Journaliser l'échec de la requête
            self.logger.warning(
                f"Request {context.method} failed after {duration_ms:.2f}ms: {type(e).__name__}: {e}"
            )
            
            # Re-lever l'exception pour ne pas interrompre le flux d'erreur
            raise 