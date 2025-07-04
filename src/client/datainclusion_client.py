"""
Client FastA2A pour l'agent IA d'inclusion sociale.

Ce module fournit une interface simple et robuste pour communiquer avec
l'agent IA d'inclusion sociale via le protocole Agent-to-Agent (A2A).
Il est optimisé pour une intégration facile avec Gradio ou d'autres frontends.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Union, AsyncGenerator, Literal
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fasta2a.client import A2AClient
from fasta2a.schema import (
    Message, Task, TaskState, SendTaskResponse, GetTaskResponse, 
    TextPart, Part, JSONRPCResponse, Artifact
)

# Configuration du logging
logger = logging.getLogger(__name__)


class DataInclusionClientError(Exception):
    """Exception de base pour les erreurs du client DataInclusion."""
    pass


class TaskNotFoundError(DataInclusionClientError):
    """Erreur levée quand une tâche n'est pas trouvée."""
    pass


class TaskFailedError(DataInclusionClientError):
    """Erreur levée quand une tâche a échoué."""
    pass


class ConnectionError(DataInclusionClientError):
    """Erreur levée en cas de problème de connexion."""
    pass


@dataclass
class ChatMessage:
    """Représente un message dans une conversation."""
    role: str  # 'user' ou 'agent'
    content: str
    timestamp: Optional[datetime] = None


@dataclass
class TaskResult:
    """Résultat d'une tâche avec métadonnées."""
    task_id: str
    status: TaskState
    messages: List[ChatMessage]
    artifacts: List[Artifact]
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DataInclusionClient:
    """
    Client robuste pour l'agent IA d'inclusion sociale via FastA2A.
    
    Ce client facilite l'interaction avec l'agent IA spécialisé dans
    l'inclusion sociale en France, permettant d'envoyer des questions
    et de recevoir des réponses structurées.
    
    Usage:
        async with DataInclusionClient("http://localhost:8001") as client:
            result = await client.ask_question("Trouve-moi des services d'aide au logement à Paris")
            print(result.messages[-1].content)
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        timeout: float = 60.0,
        max_retries: int = 3,
        poll_interval: float = 1.0
    ):
        """
        Initialise le client DataInclusion.
        
        Args:
            base_url: URL de base du serveur agent (par défaut: http://localhost:8001)
            timeout: Timeout en secondes pour les requêtes HTTP (par défaut: 60.0)
            max_retries: Nombre maximum de tentatives en cas d'erreur (par défaut: 3)
            poll_interval: Intervalle de polling en secondes pour vérifier l'état des tâches (par défaut: 1.0)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.poll_interval = poll_interval
        
        # Configuration du client HTTP avec retry automatique
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        # Client A2A pour la communication avec le serveur
        self._a2a_client = A2AClient(
            base_url=base_url,
            http_client=self._http_client
        )
        
        self._closed = False
    
    async def __aenter__(self):
        """Entre dans le contexte asynchrone."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Sort du contexte asynchrone et ferme les connexions."""
        await self.close()
    
    async def close(self):
        """Ferme les connexions HTTP proprement."""
        if not self._closed:
            await self._http_client.aclose()
            self._closed = True
    
    def _create_message(self, content: str, role: str = "user") -> Message:
        """
        Crée un message au format A2A.
        
        Args:
            content: Contenu du message
            role: Rôle du message ('user' ou 'agent')
            
        Returns:
            Message formaté pour le protocole A2A
        """
        text_part: TextPart = {"type": "text", "text": content}
        return {
            "role": role,  # type: ignore
            "parts": [text_part],
            "metadata": {}
        }
    
    def _parse_task_result(self, task: Task) -> TaskResult:
        """
        Parse un objet Task en TaskResult pour un usage plus simple.
        
        Args:
            task: Tâche A2A
            
        Returns:
            TaskResult parsé et structuré
        """
        # Extraire les messages
        messages = []
        history = task.get('history')
        if history and isinstance(history, list):
            for msg in history:
                if not isinstance(msg, dict):
                    continue
                    
                content = ""
                # Extraire le texte de toutes les parties du message
                parts = msg.get('parts')
                if parts and isinstance(parts, list):
                    for part in parts:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            text = part.get('text')
                            if text:
                                content += str(text)
                
                messages.append(ChatMessage(
                    role=msg.get('role', 'unknown'),
                    content=content.strip(),
                    timestamp=datetime.now(timezone.utc)
                ))
        
        # Extraire les timestamps
        created_at = None
        completed_at = None
        task_status = task.get('status', {})
        timestamp_str = task_status.get('timestamp')
        if timestamp_str and isinstance(timestamp_str, str):
            try:
                created_at = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        if task['status']['state'] in ['completed', 'failed', 'canceled']:
            completed_at = created_at
        
        return TaskResult(
            task_id=task['id'],
            status=task['status']['state'],
            messages=messages,
            artifacts=task.get('artifacts', []),
            metadata=task.get('metadata'),
            created_at=created_at,
            completed_at=completed_at
        )
    
    def _extract_task_from_response(self, response: Union[SendTaskResponse, GetTaskResponse]) -> Task:
        """
        Extrait la tâche d'une réponse JSON-RPC.
        
        Args:
            response: Réponse JSON-RPC contenant soit un résultat soit une erreur
            
        Returns:
            Task: L'objet Task extrait
            
        Raises:
            TaskNotFoundError: Si la tâche n'est pas trouvée ou s'il y a une erreur
        """
        # Vérifier s'il y a une erreur dans la réponse JSON-RPC
        if 'error' in response:
            error = response['error']
            if hasattr(error, 'get'):
                error_message = error.get('message', 'Erreur inconnue')
            else:
                error_message = str(error)
            raise TaskNotFoundError(f"Erreur dans la réponse: {error_message}")
        
        # Extraire le résultat de la réponse JSON-RPC
        if 'result' not in response:
            raise TaskNotFoundError("Aucun résultat dans la réponse")
        
        task = response['result']
        if not isinstance(task, dict) or 'id' not in task:
            raise TaskNotFoundError("Réponse invalide: n'est pas une tâche valide")
        
        return task  # type: ignore
    
    async def _wait_for_completion(
        self,
        task_id: str,
        max_wait_time: Optional[float] = None
    ) -> TaskResult:
        """
        Attend qu'une tâche soit terminée en utilisant le polling.
        
        Args:
            task_id: ID de la tâche à surveiller
            max_wait_time: Temps maximum d'attente en secondes (None = illimité)
            
        Returns:
            TaskResult une fois la tâche terminée
            
        Raises:
            TaskFailedError: Si la tâche échoue
            ConnectionError: En cas de problème de connexion
            asyncio.TimeoutError: Si max_wait_time est dépassé
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            try:
                # Vérifier l'état de la tâche
                response = await self._a2a_client.get_task(task_id)
                task = self._extract_task_from_response(response)
                task_result = self._parse_task_result(task)
                
                # Vérifier si la tâche est terminée
                if task_result.status in ['completed', 'failed', 'canceled']:
                    if task_result.status == 'failed':
                        status_message = task.get('status', {}).get('message', 'Tâche échouée')
                        raise TaskFailedError(f"La tâche a échoué: {status_message}")
                    elif task_result.status == 'canceled':
                        raise TaskFailedError("La tâche a été annulée")
                    
                    logger.info(f"Tâche {task_id} terminée avec succès")
                    return task_result
                
                # Vérifier le timeout
                if max_wait_time:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > max_wait_time:
                        raise asyncio.TimeoutError(f"Timeout de {max_wait_time}s dépassé pour la tâche {task_id}")
                
                # Attendre avant la prochaine vérification
                await asyncio.sleep(self.poll_interval)
                
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error(f"Erreur lors de la vérification de la tâche {task_id}: {e}")
                raise ConnectionError(f"Impossible de vérifier l'état de la tâche: {e}")
    
    async def ask_question(
        self,
        question: str,
        session_id: Optional[str] = None,
        history_length: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        wait_for_completion: bool = True,
        max_wait_time: Optional[float] = None
    ) -> TaskResult:
        """
        Pose une question à l'agent IA d'inclusion sociale.
        
        Args:
            question: Question à poser à l'agent
            session_id: ID de session optionnel pour maintenir le contexte
            history_length: Nombre de messages précédents à inclure
            metadata: Métadonnées optionnelles
            wait_for_completion: Si True, attend que la tâche soit terminée
            max_wait_time: Temps maximum d'attente en secondes
            
        Returns:
            TaskResult avec la réponse de l'agent
            
        Raises:
            DataInclusionClientError: En cas d'erreur lors de l'envoi ou du traitement
        """
        if self._closed:
            raise DataInclusionClientError("Le client a été fermé")
        
        logger.info(f"Envoi de la question: {question[:100]}{'...' if len(question) > 100 else ''}")
        
        try:
            # Créer le message
            message = self._create_message(question)
            
            # Envoyer la tâche
            response = await self._a2a_client.send_task(
                message=message,
                history_length=history_length,
                metadata=metadata
            )
            
            # Extraire la tâche de la réponse
            task = self._extract_task_from_response(response)
            task_id = task['id']
            logger.info(f"Tâche créée avec l'ID: {task_id}")
            
            # Si on doit attendre la complétion
            if wait_for_completion:
                return await self._wait_for_completion(task_id, max_wait_time)
            else:
                # Retourner immédiatement l'état initial
                return self._parse_task_result(task)
                
        except Exception as e:
            # Gérer les exceptions du client A2A
            if isinstance(e, httpx.HTTPStatusError):
                logger.error(f"Réponse inattendue du serveur: {e.response.status_code} - {e.response.text}")
                raise ConnectionError(f"Erreur HTTP {e.response.status_code}: {e.response.text}")
            elif isinstance(e, (httpx.RequestError, httpx.ConnectError)):
                logger.error(f"Erreur de connexion: {e}")
                raise ConnectionError(f"Impossible de se connecter au serveur: {e}")
            else:
                # Re-raise les erreurs que nous avons déjà définies
                raise
    
    async def get_task_status(self, task_id: str) -> TaskResult:
        """
        Récupère l'état d'une tâche existante.
        
        Args:
            task_id: ID de la tâche à vérifier
            
        Returns:
            TaskResult avec l'état actuel de la tâche
            
        Raises:
            TaskNotFoundError: Si la tâche n'existe pas
            ConnectionError: En cas de problème de connexion
        """
        if self._closed:
            raise DataInclusionClientError("Le client a été fermé")
        
        try:
            response = await self._a2a_client.get_task(task_id)
            task = self._extract_task_from_response(response)
            return self._parse_task_result(task)
            
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"Erreur lors de la récupération de la tâche {task_id}: {e}")
            raise ConnectionError(f"Impossible de récupérer l'état de la tâche: {e}")
    
    async def stream_conversation(
        self,
        questions: List[str],
        session_id: Optional[str] = None
    ) -> AsyncGenerator[TaskResult, None]:
        """
        Envoie une série de questions et yield les résultats au fur et à mesure.
        
        Args:
            questions: Liste des questions à poser séquentiellement
            session_id: ID de session pour maintenir le contexte
            
        Yields:
            TaskResult pour chaque question posée
            
        Raises:
            DataInclusionClientError: En cas d'erreur
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        for i, question in enumerate(questions):
            logger.info(f"Question {i+1}/{len(questions)}: {question[:50]}{'...' if len(question) > 50 else ''}")
            
            result = await self.ask_question(
                question=question,
                session_id=session_id,
                history_length=10  # Garder les 10 derniers messages pour le contexte
            )
            
            yield result
    
    async def check_server_health(self) -> bool:
        """
        Vérifie si le serveur est accessible et fonctionne.
        
        Returns:
            True si le serveur est accessible, False sinon
        """
        try:
            # Tenter de récupérer la carte de l'agent
            response = await self._http_client.get(f"{self.base_url}/.well-known/agent.json")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Vérification de santé du serveur échouée: {e}")
            return False
    
    @asynccontextmanager
    async def conversation_session(self, session_id: Optional[str] = None):
        """
        Gestionnaire de contexte pour une session de conversation.
        
        Args:
            session_id: ID de session optionnel
            
        Yields:
            Une fonction ask qui maintient le contexte de session
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        logger.info(f"Début de session de conversation: {session_id}")
        
        async def ask(question: str, **kwargs) -> TaskResult:
            """Fonction ask avec session maintenue."""
            return await self.ask_question(
                question=question,
                session_id=session_id,
                history_length=kwargs.pop('history_length', 10),
                **kwargs
            )
        
        try:
            yield ask
        finally:
            logger.info(f"Fin de session de conversation: {session_id}")


# Fonction utilitaire pour une utilisation simple
async def quick_ask(
    question: str,
    server_url: str = "http://localhost:8001",
    timeout: float = 60.0
) -> str:
    """
    Fonction utilitaire pour poser une question rapidement sans gérer le client.
    
    Args:
        question: Question à poser
        server_url: URL du serveur agent
        timeout: Timeout en secondes
        
    Returns:
        Réponse de l'agent sous forme de texte
        
    Raises:
        DataInclusionClientError: En cas d'erreur
    """
    async with DataInclusionClient(server_url, timeout=timeout) as client:
        result = await client.ask_question(question)
        
        # Retourner le dernier message de l'agent
        for msg in reversed(result.messages):
            if msg.role == 'agent':
                return msg.content
        
        return "Aucune réponse de l'agent" 