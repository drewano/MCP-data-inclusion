/**
 * Hooks React pour faciliter l'utilisation du client A2A
 * Intégration avec React et gestion d'état automatique
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  A2AClient,
  createDevelopmentA2AClient,
  createProductionA2AClient,
  createA2AClient,
  canCreateA2AClient,
  type AgentCard,
  type Task,
  type TaskSendParams,
  type StreamingEvent,
  type TaskQueryParams,
  type TaskIdParams,
  type A2AClientOptions,
  RpcError,
  NetworkError,
  TimeoutError,
  AuthenticationError,
  TaskError,
  isTaskStatusUpdateEvent,
  isTaskArtifactUpdateEvent,
  isTerminalTaskState,
  createUserMessage,
  generateTaskId,
} from '@/lib/api';

// ============================================================================
// Types pour les hooks
// ============================================================================

/**
 * État d'une requête A2A
 */
export type RequestState<T> = {
  data: T | null;
  loading: boolean;
  error: Error | null;
};

/**
 * Options pour les hooks de streaming
 */
export interface UseStreamingOptions {
  /** Désactiver le démarrage automatique */
  manual?: boolean;
  
  /** Callback appelé pour chaque événement */
  onEvent?: (event: StreamingEvent) => void;
  
  /** Callback appelé en cas d'erreur */
  onError?: (error: Error) => void;
  
  /** Callback appelé à la fin du stream */
  onEnd?: () => void;
}

/**
 * État d'un stream A2A
 */
export interface StreamState {
  isStreaming: boolean;
  events: StreamingEvent[];
  error: Error | null;
  lastEvent: StreamingEvent | null;
}

// ============================================================================
// Hook principal pour le client A2A
// ============================================================================

/**
 * Hook principal pour obtenir une instance du client A2A
 */
export function useA2AClient(options?: A2AClientOptions): A2AClient | null {
  const [client, setClient] = useState<A2AClient | null>(null);
  const [isClient, setIsClient] = useState(false);

  // Détecter quand on est côté client
  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    // Ne créer le client que côté client
    if (!isClient) return;

    // Vérifier que l'environnement supporte A2A
    if (!canCreateA2AClient()) {
      console.warn('A2A client cannot be created in this environment (missing window or fetch)');
      return;
    }

    try {
      const clientInstance = createA2AClient({
        agentPort: 8001, // Port par défaut pour le développement
        ...options,
      });
      setClient(clientInstance);
      console.log('Client A2A initialisé avec succès');
    } catch (error) {
      console.error("Erreur lors de la création du client A2A:", error);
    }
  }, [isClient, options]);

  return client;
}

// ============================================================================
// Hook pour la carte d'agent
// ============================================================================

/**
 * Hook pour récupérer la carte d'identité de l'agent
 */
export function useAgentCard(client?: A2AClient): RequestState<AgentCard> {
  const defaultClient = useA2AClient();
  const a2aClient = client || defaultClient;
  
  const [state, setState] = useState<RequestState<AgentCard>>({
    data: null,
    loading: false,
    error: null,
  });

  const fetchAgentCard = useCallback(async () => {
    if (!a2aClient) return;
    
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const card = await a2aClient.getAgentCard();
      setState({ data: card, loading: false, error: null });
    } catch (error) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error : new Error(String(error))
      }));
    }
  }, [a2aClient]);

  useEffect(() => {
    fetchAgentCard();
  }, [fetchAgentCard]);

  return state;
}

// ============================================================================
// Hook pour l'envoi de tâches
// ============================================================================

/**
 * Hook pour envoyer des tâches (non-streaming)
 */
export function useSendTask(client?: A2AClient) {
  const defaultClient = useA2AClient();
  const a2aClient = client || defaultClient;
  
  const [state, setState] = useState<RequestState<Task>>({
    data: null,
    loading: false,
    error: null,
  });

  const sendTask = useCallback(async (params: TaskSendParams): Promise<Task | null> => {
    if (!a2aClient) {
      throw new Error('A2A client is not yet initialized.');
    }
    
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const task = await a2aClient.sendTask(params);
      setState({ data: task, loading: false, error: null });
      return task;
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      setState(prev => ({ ...prev, loading: false, error: err }));
      throw err;
    }
  }, [a2aClient]);

  const sendUserMessage = useCallback(async (text: string, metadata?: Record<string, unknown>): Promise<Task | null> => {
    const taskId = generateTaskId();
    const message = createUserMessage(text, metadata);
    
    return sendTask({ id: taskId, message });
  }, [sendTask]);

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
  }, []);

  return {
    ...state,
    sendTask,
    sendUserMessage,
    reset,
  };
}

// ============================================================================
// Hook pour le streaming
// ============================================================================

/**
 * Hook pour le streaming de tâches
 */
export function useTaskStreaming(
  client?: A2AClient,
  options: UseStreamingOptions = {}
) {
  const defaultClient = useA2AClient();
  const a2aClient = client || defaultClient;
  
  const [state, setState] = useState<StreamState>({
    isStreaming: false,
    events: [],
    error: null,
    lastEvent: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const { onEvent, onError, onEnd } = options;

  const startStreaming = useCallback(async (params: TaskSendParams) => {
    if (!a2aClient) {
      throw new Error('A2A client is not yet initialized.');
    }
    
    // Annuler le stream précédent s'il existe
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    setState(prev => ({
      ...prev,
      isStreaming: true,
      error: null,
      events: [],
      lastEvent: null,
    }));

    try {
      const stream = a2aClient.sendTaskSubscribe(params);

      for await (const event of stream) {
        if (signal.aborted) break;

        setState(prev => ({
          ...prev,
          events: [...prev.events, event],
          lastEvent: event,
        }));

        onEvent?.(event);

        // Arrêter le streaming si la tâche est terminée
        if (isTaskStatusUpdateEvent(event) && isTerminalTaskState(event.status.state)) {
          break;
        }
      }

      setState(prev => ({ ...prev, isStreaming: false }));
      onEnd?.();

    } catch (error) {
      if (signal.aborted) return; // Ignore les erreurs d'annulation
      
      const err = error instanceof Error ? error : new Error(String(error));
      setState(prev => ({
        ...prev,
        isStreaming: false,
        error: err,
      }));
      onError?.(err);
    }
  }, [a2aClient, onEvent, onError, onEnd]);

  const streamUserMessage = useCallback(async (text: string, metadata?: Record<string, unknown>) => {
    const taskId = generateTaskId();
    const message = createUserMessage(text, metadata);
    
    return startStreaming({ id: taskId, message });
  }, [startStreaming]);

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setState(prev => ({ ...prev, isStreaming: false }));
  }, []);

  const reset = useCallback(() => {
    stopStreaming();
    setState({
      isStreaming: false,
      events: [],
      error: null,
      lastEvent: null,
    });
  }, [stopStreaming]);

  // Nettoyer à la destruction du composant
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    ...state,
    startStreaming,
    streamUserMessage,
    stopStreaming,
    reset,
  };
}

// ============================================================================
// Hook pour la gestion des tâches
// ============================================================================

/**
 * Hook pour gérer une tâche spécifique
 */
export function useTask(taskId: string, client?: A2AClient) {
  const defaultClient = useA2AClient();
  const a2aClient = client || defaultClient;
  
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const getTask = useCallback(async (params?: Omit<TaskQueryParams, 'id'>): Promise<Task | null> => {
    if (!a2aClient) {
      throw new Error('A2A client is not yet initialized.');
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await a2aClient.getTask({ id: taskId, ...params });
      setTask(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [a2aClient, taskId]);

  const cancelTask = useCallback(async (): Promise<Task | null> => {
    if (!a2aClient) {
      throw new Error('A2A client is not yet initialized.');
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await a2aClient.cancelTask({ id: taskId });
      setTask(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [a2aClient, taskId]);

  const resubscribe = useCallback((params?: Omit<TaskQueryParams, 'id'>): AsyncIterable<StreamingEvent> => {
    if (!a2aClient) {
      throw new Error('A2A client is not yet initialized.');
    }
    return a2aClient.resubscribeTask({ id: taskId, ...params });
  }, [a2aClient, taskId]);

  // Charger la tâche au montage
  useEffect(() => {
    if (taskId) {
      getTask();
    }
  }, [taskId, getTask]);

  return {
    task,
    loading,
    error,
    getTask,
    cancelTask,
    resubscribe,
  };
}

// ============================================================================
// Hook utilitaire pour les événements de streaming
// ============================================================================

/**
 * Hook pour traiter les événements de streaming
 */
export function useStreamingEventProcessor() {
  const processEvent = useCallback((event: StreamingEvent) => {
    if (isTaskStatusUpdateEvent(event)) {
      return {
        type: 'status' as const,
        event,
        taskId: event.id,
        state: event.status.state,
        message: event.status.message,
        isFinal: event.final || false,
        isTerminal: isTerminalTaskState(event.status.state),
      };
    } else if (isTaskArtifactUpdateEvent(event)) {
      return {
        type: 'artifact' as const,
        event,
        taskId: event.id,
        artifact: event.artifact,
        isFinal: event.final || false,
      };
    } else {
      return {
        type: 'unknown' as const,
        event,
        taskId: 'id' in event ? (event as { id: string }).id : 'unknown',
      };
    }
  }, []);

  return { processEvent };
}

// ============================================================================
// Hook pour la gestion des erreurs A2A
// ============================================================================

/**
 * Hook pour gérer les erreurs A2A de manière centralisée
 */
export function useA2AErrorHandler() {
  const handleError = useCallback((error: Error): string => {
    if (error instanceof RpcError) {
      console.error('RPC Error:', {
        code: error.code,
        message: error.message,
        data: error.data,
        taskId: error.taskId,
      });
      
      // Traitement spécifique selon le code d'erreur
      switch (error.code) {
        case -32001: // TASK_NOT_FOUND
          return 'Tâche non trouvée';
        case -32002: // TASK_NOT_CANCELABLE
          return 'Cette tâche ne peut pas être annulée';
        case -32003: // PUSH_NOTIFICATION_NOT_SUPPORTED
          return 'Les notifications push ne sont pas supportées';
        case -32004: // UNSUPPORTED_OPERATION
          return 'Opération non supportée';
        default:
          return `Erreur RPC: ${error.message}`;
      }
    } else if (error instanceof NetworkError) {
      console.error('Network Error:', error.originalError);
      return 'Erreur de réseau. Vérifiez votre connexion.';
    } else if (error instanceof TimeoutError) {
      console.error('Timeout Error:', error.timeout);
      return `Timeout après ${error.timeout}ms. Réessayez.`;
    } else if (error instanceof AuthenticationError) {
      console.error('Authentication Error:', error.message);
      return 'Erreur d\'authentification. Vérifiez vos identifiants.';
    } else if (error instanceof TaskError) {
      console.error('Task Error:', error.message, 'Task ID:', error.taskId, 'State:', error.taskState);
      return `Erreur de tâche: ${error.message}`;
    } else {
      console.error('Unknown Error:', error);
      return `Erreur inattendue: ${error.message}`;
    }
  }, []);

  return { handleError };
} 