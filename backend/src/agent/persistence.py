"""
Redis-based implementations for Storage and Broker.

Ce module fournit des implémentations Redis pour les classes abstraites
Storage et Broker de fasta2a, permettant la persistance des tâches et 
la messagerie via Redis.
"""

import json
import logging
from typing import AsyncIterator, Any, Dict, List, Union, TypedDict, Literal, NotRequired, cast
from datetime import datetime
import asyncio

import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from fasta2a.storage import Storage
from fasta2a.broker import Broker

logger = logging.getLogger(__name__)


# Types pour remplacer les imports de fasta2a.types selon la documentation
TaskState = Literal[
    "submitted",
    "working", 
    "input-required",
    "completed",
    "canceled",
    "failed",
    "unknown",
]


class TaskStatus(TypedDict):
    """Current status of the task."""
    state: TaskState
    message: NotRequired[str]
    timestamp: NotRequired[datetime]


class Message(TypedDict):
    """A message within a task."""
    role: Literal['user', 'agent']
    parts: List[Dict[str, Any]]  # Parts simplifiés pour l'instant
    metadata: NotRequired[Dict[str, Any]]


class Artifact(TypedDict):
    """Agents generate Artifacts as an end result of a Task."""
    name: NotRequired[str]
    description: NotRequired[str]
    parts: List[Dict[str, Any]]  # Parts simplifiés pour l'instant
    metadata: NotRequired[Dict[str, Any]]
    index: int
    append: NotRequired[bool]
    last_chunk: NotRequired[bool]


class Task(TypedDict):
    """A Task is a stateful entity that allows Clients and Remote Agents to achieve a specific outcome."""
    id: str
    session_id: NotRequired[str]
    status: TaskStatus
    history: NotRequired[List[Message]]
    artifacts: NotRequired[List[Artifact]]
    metadata: NotRequired[Dict[str, Any]]


class TaskSendParams(TypedDict):
    """Sent by the client to the agent to create, continue, or restart a task."""
    id: str
    session_id: NotRequired[str]
    message: Message
    history_length: NotRequired[int]
    push_notification: NotRequired[Dict[str, Any]]  # PushNotificationConfig simplifié
    metadata: NotRequired[Dict[str, Any]]


class TaskIdParams(TypedDict):
    """Parameters for a task id."""
    id: str
    metadata: NotRequired[Dict[str, Any]]


class TaskOperation(TypedDict):
    """Opération de tâche pour le broker."""
    operation: str
    params: Union[TaskSendParams, TaskIdParams]
    _current_span: Any


class RedisStorage(Storage):
    """
    Implémentation Redis robuste de l'interface Storage de fasta2a.
    
    Utilise Redis pour stocker les données des tâches sous forme de JSON
    avec TTL automatique, retry avec backoff exponentiel, et gestion d'erreurs robuste.
    """
    
    def __init__(
        self, 
        redis_client: redis.Redis,
        task_ttl: int = 7 * 24 * 3600,  # 7 jours par défaut
        max_retries: int = 3
    ):
        """
        Initialise le storage Redis.
        
        Args:
            redis_client: Client Redis asynchrone configuré
            task_ttl: TTL en secondes pour les tâches (défaut: 7 jours)
            max_retries: Nombre maximum de tentatives en cas d'erreur
        """
        self.redis_client = redis_client
        self._task_prefix = "fasta2a:task:"
        self._task_ttl = task_ttl
        self._max_retries = max_retries
        self._retry_strategy = Retry(ExponentialBackoff(), max_retries)
    
    def _get_task_key(self, task_id: str) -> str:
        """Génère la clé Redis pour une tâche."""
        return f"{self._task_prefix}{task_id}"
    
    async def load_task(self, task_id: str, history_length: int | None = None) -> Task | None:
        """
        Charge une tâche depuis Redis avec retry automatique.
        
        Args:
            task_id: ID de la tâche à charger
            history_length: Longueur de l'historique à récupérer
            
        Returns:
            Task object ou None si la tâche n'existe pas
        """
        if not task_id or not isinstance(task_id, str):
            logger.error(f"Invalid task_id: {task_id}")
            return None
            
        key = self._get_task_key(task_id)
        
        for attempt in range(self._max_retries + 1):
            try:
                task_data = await self.redis_client.get(key)
                
                if task_data is None:
                    logger.debug(f"Task {task_id} not found in Redis")
                    return None
                
                # Désérialiser le JSON
                task_dict = json.loads(task_data)
                
                # Validation de base de la structure
                if not isinstance(task_dict, dict) or "id" not in task_dict:
                    logger.error(f"Invalid task structure for {task_id}")
                    return None
                
                # Limiter l'historique si demandé
                if history_length is not None and "history" in task_dict and task_dict["history"]:
                    task_dict["history"] = task_dict["history"][-history_length:]
                
                # Reconstituer les types datetime si nécessaire
                if "status" in task_dict and "timestamp" in task_dict["status"]:
                    if isinstance(task_dict["status"]["timestamp"], str):
                        task_dict["status"]["timestamp"] = datetime.fromisoformat(task_dict["status"]["timestamp"])
                
                logger.debug(f"Loaded task {task_id} from Redis")
                return cast(Task, task_dict)
                
            except (RedisConnectionError, RedisTimeoutError) as e:
                if attempt < self._max_retries:
                    wait_time = 2 ** attempt  # backoff exponentiel
                    logger.warning(f"Redis error loading task {task_id} (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to load task {task_id} after {self._max_retries + 1} attempts: {e}")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for task {task_id}: {e}")
                return None
                
            except Exception as e:
                logger.error(f"Unexpected error loading task {task_id}: {e}")
                return None
                
        return None
    
    async def submit_task(self, task_id: str, session_id: str, message: Message) -> Task:
        """
        Soumet une nouvelle tâche au storage avec retry automatique.
        
        Args:
            task_id: ID unique de la tâche
            session_id: ID de la session associée
            message: Message initial de la tâche
            
        Returns:
            Task object créé
            
        Raises:
            Exception: Si la soumission échoue après tous les retries
        """
        if not task_id or not isinstance(task_id, str):
            raise ValueError(f"Invalid task_id: {task_id}")
        if not session_id or not isinstance(session_id, str):
            raise ValueError(f"Invalid session_id: {session_id}")
        if not message or not isinstance(message, dict):
            raise ValueError(f"Invalid message: {message}")
            
        now = datetime.utcnow()
        
        # Créer l'objet Task conforme au schéma fasta2a
        task: Task = {
            "id": task_id,
            "session_id": session_id,
            "status": {
                "state": "submitted",
                "message": "Task submitted successfully",
                "timestamp": now
            },
            "history": [message],
            "artifacts": [],
            "metadata": {}
        }
        
        # Sérialiser en JSON avec gestion des datetime
        task_json = json.dumps(task, default=self._json_serializer)
        key = self._get_task_key(task_id)
        
        for attempt in range(self._max_retries + 1):
            try:
                # Stocker dans Redis avec TTL
                await self.redis_client.set(key, task_json, ex=self._task_ttl)
                
                logger.info(f"Submitted task {task_id} to Redis with TTL {self._task_ttl}s")
                return task
                
            except (RedisConnectionError, RedisTimeoutError) as e:
                if attempt < self._max_retries:
                    wait_time = 2 ** attempt  # backoff exponentiel
                    logger.warning(f"Redis error submitting task {task_id} (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to submit task {task_id} after {self._max_retries + 1} attempts: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error submitting task {task_id}: {e}")
                raise
        
        # Ce point ne devrait jamais être atteint
        raise RuntimeError(f"Failed to submit task {task_id} - unexpected code path")
    
    async def update_task(
        self,
        task_id: str,
        state: TaskState,
        message: Message | None = None,
        artifacts: List[Artifact] | None = None,
    ) -> Task:
        """
        Met à jour l'état d'une tâche avec retry automatique.
        
        Args:
            task_id: ID de la tâche à mettre à jour
            state: Nouvel état de la tâche
            message: Message optionnel à ajouter à l'historique
            artifacts: Artifacts optionnels à ajouter
            
        Returns:
            Task object mis à jour
            
        Raises:
            ValueError: Si la tâche n'existe pas
            Exception: Si la mise à jour échoue après tous les retries
        """
        if not task_id or not isinstance(task_id, str):
            raise ValueError(f"Invalid task_id: {task_id}")
        if not state or state not in ["submitted", "working", "input-required", "completed", "canceled", "failed", "unknown"]:
            raise ValueError(f"Invalid state: {state}")
        
        # Charger la tâche existante
        task = await self.load_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found for update")
        
        now = datetime.utcnow()
        
        # Mettre à jour le status
        task["status"] = {
            "state": state,
            "message": f"Task state updated to {state}",
            "timestamp": now
        }
        
        # Ajouter le message à l'historique si fourni
        if message is not None:
            if "history" not in task:
                task["history"] = []
            task["history"].append(message)
        
        # Ajouter les artifacts si fournis
        if artifacts is not None:
            if "artifacts" not in task:
                task["artifacts"] = []
            task["artifacts"].extend(artifacts)
        
        # Sauvegarder la tâche mise à jour avec retry
        task_json = json.dumps(task, default=self._json_serializer)
        key = self._get_task_key(task_id)
        
        for attempt in range(self._max_retries + 1):
            try:
                # Sauvegarder avec TTL
                await self.redis_client.set(key, task_json, ex=self._task_ttl)
                
                logger.info(f"Updated task {task_id} state to {state}")
                return cast(Task, task)
                
            except (RedisConnectionError, RedisTimeoutError) as e:
                if attempt < self._max_retries:
                    wait_time = 2 ** attempt  # backoff exponentiel
                    logger.warning(f"Redis error updating task {task_id} (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to update task {task_id} after {self._max_retries + 1} attempts: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error updating task {task_id}: {e}")
                raise
        
        # Ce point ne devrait jamais être atteint
        raise RuntimeError(f"Failed to update task {task_id} - unexpected code path")
    
    def _json_serializer(self, obj):
        """Sérialiseur JSON personnalisé pour gérer les types datetime."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class RedisBroker(Broker):
    """
    Implémentation Redis robuste de l'interface Broker de fasta2a.
    
    Utilise Redis Pub/Sub pour la messagerie entre composants avec
    reconnexion automatique, retry avec backoff, et gestion d'erreurs.
    """
    
    def __init__(
        self, 
        redis_client: redis.Redis,
        channel_name: str = "fasta2a:tasks",
        max_retries: int = 3,
        reconnect_interval: int = 5
    ):
        """
        Initialise le broker Redis.
        
        Args:
            redis_client: Client Redis asynchrone configuré
            channel_name: Nom du canal Pub/Sub à utiliser
            max_retries: Nombre maximum de tentatives en cas d'erreur
            reconnect_interval: Intervalle de reconnexion en secondes
        """
        self.redis_client = redis_client
        self._task_channel = channel_name
        self._max_retries = max_retries
        self._reconnect_interval = reconnect_interval
        self._pubsub = None
        self._is_listening = False
    
    async def run_task(self, params: TaskSendParams) -> None:
        """
        Publie une opération de lancement de tâche avec retry automatique.
        
        Args:
            params: Paramètres de la tâche à lancer
            
        Raises:
            Exception: Si la publication échoue après tous les retries
        """
        if not params or not isinstance(params, dict):
            raise ValueError(f"Invalid params: {params}")
        
        task_id = params.get('id', 'unknown')
        
        task_operation: TaskOperation = {
            "operation": "run",
            "params": params,
            "_current_span": None  # Peut être adapté selon vos besoins de tracing
        }
        
        # Sérialiser l'opération
        operation_json = json.dumps(task_operation, default=self._json_serializer)
        
        for attempt in range(self._max_retries + 1):
            try:
                # Publier sur le canal Redis
                result = await self.redis_client.publish(self._task_channel, operation_json)
                
                logger.debug(f"Published run_task operation for task {task_id}, {result} subscribers notified")
                return
                
            except (RedisConnectionError, RedisTimeoutError) as e:
                if attempt < self._max_retries:
                    wait_time = 2 ** attempt  # backoff exponentiel
                    logger.warning(f"Redis error publishing run_task for {task_id} (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to publish run_task for {task_id} after {self._max_retries + 1} attempts: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error publishing run_task for {task_id}: {e}")
                raise
        
        # Ce point ne devrait jamais être atteint
        raise RuntimeError(f"Failed to publish run_task for {task_id} - unexpected code path")
    
    async def cancel_task(self, params: TaskIdParams) -> None:
        """
        Publie une opération d'annulation de tâche avec retry automatique.
        
        Args:
            params: Paramètres contenant l'ID de la tâche à annuler
            
        Raises:
            Exception: Si la publication échoue après tous les retries
        """
        if not params or not isinstance(params, dict):
            raise ValueError(f"Invalid params: {params}")
        
        task_id = params.get('id', 'unknown')
        
        task_operation: TaskOperation = {
            "operation": "cancel", 
            "params": params,
            "_current_span": None  # Peut être adapté selon vos besoins de tracing
        }
        
        # Sérialiser l'opération
        operation_json = json.dumps(task_operation, default=self._json_serializer)
        
        for attempt in range(self._max_retries + 1):
            try:
                # Publier sur le canal Redis
                result = await self.redis_client.publish(self._task_channel, operation_json)
                
                logger.debug(f"Published cancel_task operation for task {task_id}, {result} subscribers notified")
                return
                
            except (RedisConnectionError, RedisTimeoutError) as e:
                if attempt < self._max_retries:
                    wait_time = 2 ** attempt  # backoff exponentiel
                    logger.warning(f"Redis error publishing cancel_task for {task_id} (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to publish cancel_task for {task_id} after {self._max_retries + 1} attempts: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error publishing cancel_task for {task_id}: {e}")
                raise
        
        # Ce point ne devrait jamais être atteint
        raise RuntimeError(f"Failed to publish cancel_task for {task_id} - unexpected code path")
    
    async def __aenter__(self):
        """Entre dans le contexte du broker avec retry automatique."""
        for attempt in range(self._max_retries + 1):
            try:
                self._pubsub = self.redis_client.pubsub()
                await self._pubsub.subscribe(self._task_channel)
                self._is_listening = True
                logger.info(f"Subscribed to Redis channel: {self._task_channel}")
                return self
                
            except (RedisConnectionError, RedisTimeoutError) as e:
                if attempt < self._max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Redis error entering broker context (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to enter broker context after {self._max_retries + 1} attempts: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error entering broker context: {e}")
                raise
        
        raise RuntimeError("Failed to enter broker context - unexpected code path")
    
    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any):
        """Sort du contexte du broker avec nettoyage robuste."""
        self._is_listening = False
        
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe(self._task_channel)
                logger.debug(f"Unsubscribed from Redis channel: {self._task_channel}")
            except Exception as e:
                logger.warning(f"Error unsubscribing from channel: {e}")
            
            try:
                await self._pubsub.close()
                logger.info("Closed Redis PubSub connection")
            except Exception as e:
                logger.warning(f"Error closing PubSub connection: {e}")
            finally:
                self._pubsub = None
    
    def receive_task_operations(self) -> AsyncIterator[TaskOperation]:
        """
        Générateur asynchrone qui reçoit les opérations de tâches.
        
        Yields:
            TaskOperation: Opérations de tâches reçues via Redis Pub/Sub
        """
        return self._task_operation_generator()
    
    async def _task_operation_generator(self) -> AsyncIterator[TaskOperation]:
        """
        Générateur interne robuste pour recevoir les opérations de tâches.
        
        Gère les reconnexions automatiques et les erreurs de réseau.
        """
        if not self._pubsub:
            raise RuntimeError("Broker must be used within async context manager")
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while self._is_listening:
            try:
                # Attendre un message du canal Redis avec timeout pour permettre la vérification périodique
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0  # timeout court pour vérifier _is_listening régulièrement
                )
                
                if message is not None and message["type"] == "message":
                    try:
                        # Désérialiser l'opération
                        operation_data = json.loads(message["data"])
                        
                        # Validation de base de la structure
                        if not isinstance(operation_data, dict) or "operation" not in operation_data:
                            logger.warning(f"Invalid task operation structure: {operation_data}")
                            continue
                        
                        task_operation: TaskOperation = cast(TaskOperation, operation_data)
                        logger.debug(f"Received task operation: {task_operation['operation']}")
                        
                        # Reset compteur d'erreurs consécutives sur succès
                        consecutive_errors = 0
                        yield task_operation
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Error deserializing task operation: {e}")
                        consecutive_errors += 1
                    except Exception as e:
                        logger.error(f"Error processing task operation: {e}")
                        consecutive_errors += 1
                        
            except (RedisConnectionError, RedisTimeoutError) as e:
                consecutive_errors += 1
                logger.warning(f"Redis connection error in task generator (error #{consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive Redis errors ({consecutive_errors}), stopping generator")
                    raise
                
                # Attendre avant de réessayer
                await asyncio.sleep(min(consecutive_errors * self._reconnect_interval, 30))
                
            except asyncio.TimeoutError:
                # Timeout normal - continuer la boucle pour vérifier _is_listening
                pass
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Unexpected error in task operation generator (error #{consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}), stopping generator")
                    raise
                
                await asyncio.sleep(min(consecutive_errors, 10))
        
        logger.info("Task operation generator stopped")
    
    def _json_serializer(self, obj):
        """Sérialiseur JSON personnalisé pour gérer les types complexes."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable") 