import { create } from 'zustand'
import { v4 as uuidv4 } from 'uuid'
import { 
  type Message, 
  type Task, 
  type StreamingEvent,
  type AgentCard,
  generateTaskId,
  createUserMessage,
  isTaskStatusUpdateEvent,
  isTaskArtifactUpdateEvent,
} from '@/lib/api'

/**
 * Interface pour un message de chat adapté au protocole A2A
 */
export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  timestamp?: Date
  // Propriétés A2A
  taskId?: string
  a2aMessage?: Message
  artifacts?: Array<{
    name?: string
    content: string
    type?: string
  }>
}

/**
 * Interface pour l'état du chat avec intégration A2A
 */
export interface ChatState {
  sessionId: string
  messages: ChatMessage[]
  isLoading: boolean
  isStreaming: boolean
  input: string
  
  // État A2A
  currentTask: Task | null
  agentCard: AgentCard | null
  streamingEvents: StreamingEvent[]
  error: string | null
}

/**
 * Interface pour les actions du chat avec intégration A2A
 */
export interface ChatActions {
  setSessionId: (sessionId: string) => void
  addMessage: (message: Omit<ChatMessage, 'id'>) => void
  setInput: (input: string) => void
  setIsLoading: (isLoading: boolean) => void
  setIsStreaming: (isStreaming: boolean) => void
  updateLastMessage: (chunk: string) => void
  clearMessages: () => void
  reset: () => void
  
  // Actions A2A
  setCurrentTask: (task: Task | null) => void
  setAgentCard: (card: AgentCard | null) => void
  addStreamingEvent: (event: StreamingEvent) => void
  setError: (error: string | null) => void
  processStreamingEvent: (event: StreamingEvent) => void
  sendUserMessage: (content: string) => ChatMessage
}

/**
 * Type combiné pour le store complet
 */
export type ChatStore = ChatState & ChatActions

/**
 * État initial du store
 */
const initialState: ChatState = {
  sessionId: uuidv4(),
  messages: [],
  isLoading: false,
  isStreaming: false,
  input: '',
  
  // État A2A
  currentTask: null,
  agentCard: null,
  streamingEvents: [],
  error: null,
}

/**
 * Store Zustand pour la gestion de l'état global du chat
 * 
 * Ce store utilise les meilleures pratiques Zustand avec:
 * - Colocated actions et state
 * - Types TypeScript stricts  
 * - Gestion immutable des mises à jour
 * - Fonctions utilitaires pour le streaming
 */
export const useChatStore = create<ChatStore>()((set) => ({
  ...initialState,

  /**
   * Met à jour l'ID de session
   */
  setSessionId: (sessionId: string) => {
    set({ sessionId })
  },

  /**
   * Ajoute un nouveau message à la liste
   * Génère automatiquement un ID unique et un timestamp
   */
  addMessage: (message: Omit<ChatMessage, 'id'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: uuidv4(),
      timestamp: new Date(),
    }
    
    set((state) => ({
      messages: [...state.messages, newMessage]
    }))
  },

  /**
   * Met à jour la valeur du champ de saisie
   */
  setInput: (input: string) => {
    set({ input })
  },

  /**
   * Change l'état de chargement
   */
  setIsLoading: (isLoading: boolean) => {
    set({ isLoading })
  },

  /**
   * Met à jour le contenu du dernier message avec un chunk de texte
   * Essentiel pour l'effet de streaming des réponses de l'IA
   */
  updateLastMessage: (chunk: string) => {
    set((state) => {
      const messages = [...state.messages]
      
      if (messages.length === 0) {
        // Si aucun message n'existe, créer un nouveau message agent
        const newMessage: ChatMessage = {
          id: uuidv4(),
          role: 'agent',
          content: chunk,
          timestamp: new Date(),
        }
        return { messages: [newMessage] }
      }
      
      // Mettre à jour le dernier message
      const lastMessageIndex = messages.length - 1
      const lastMessage = messages[lastMessageIndex]
      
      messages[lastMessageIndex] = {
        ...lastMessage,
        content: lastMessage.content + chunk,
      }
      
      return { messages }
    })
  },

  /**
   * Vide tous les messages du chat
   */
  clearMessages: () => {
    set({ messages: [] })
  },

  /**
   * Remet le store à son état initial
   * Génère un nouveau sessionId
   */
  reset: () => {
    set({
      ...initialState,
      sessionId: uuidv4(), // Générer un nouveau sessionId à chaque reset
    })
  },

  /**
   * Change l'état de streaming
   */
  setIsStreaming: (isStreaming: boolean) => {
    set({ isStreaming })
  },

  /**
   * Met à jour la tâche courante A2A
   */
  setCurrentTask: (task: Task | null) => {
    set({ currentTask: task })
  },

  /**
   * Met à jour la carte d'identité de l'agent
   */
  setAgentCard: (card: AgentCard | null) => {
    set({ agentCard: card })
  },

  /**
   * Ajoute un nouvel événement de streaming
   */
  addStreamingEvent: (event: StreamingEvent) => {
    set((state) => ({
      streamingEvents: [...state.streamingEvents, event]
    }))
  },

  /**
   * Met à jour le message d'erreur
   */
  setError: (error: string | null) => {
    set({ error })
  },

  /**
   * Traite un événement de streaming et met à jour l'état correspondant
   */
  processStreamingEvent: (event: StreamingEvent) => {
    set((state) => {
      const newState = { ...state }
      
      // Ajouter l'événement à la liste
      newState.streamingEvents = [...state.streamingEvents, event]
      
      // Traitement spécifique selon le type d'événement
      if (isTaskStatusUpdateEvent(event)) {
        if (event.status.state === 'completed' || event.status.state === 'failed') {
          newState.isStreaming = false
          newState.isLoading = false
        }
      } else if (isTaskArtifactUpdateEvent(event)) {
        // Mettre à jour le contenu du dernier message avec le nouvel artifact
        const artifact = event.artifact
        if (artifact.parts && artifact.parts.length > 0 && state.messages.length > 0) {
          const messages = [...state.messages]
          const lastMessageIndex = messages.length - 1
          const lastMessage = messages[lastMessageIndex]
          
          if (lastMessage.role === 'agent') {
            // Extraire le contenu text des parts de l'artifact
            const textContent = artifact.parts
              .filter(part => part.type === 'text')
              .map(part => ('text' in part ? part.text : ''))
              .join('')
            
            messages[lastMessageIndex] = {
              ...lastMessage,
              content: textContent || lastMessage.content,
              artifacts: [{
                name: artifact.name || undefined,
                content: textContent,
                type: 'text'
              }]
            }
            newState.messages = messages
          }
        }
      }
      
      return newState
    })
  },

  /**
   * Crée et ajoute un message utilisateur avec intégration A2A
   */
  sendUserMessage: (content: string) => {
    const taskId = generateTaskId()
    const a2aMessage = createUserMessage(content)
    
    const message: ChatMessage = {
      id: uuidv4(),
      role: 'user',
      content,
      timestamp: new Date(),
      taskId,
      a2aMessage,
    }
    
    // Ajouter le message à l'état
    set((state) => ({
      messages: [...state.messages, message],
      input: '', // Clear input après envoi
    }))
    
    return message
  },
}))

/**
 * Sélecteurs utilitaires pour accéder facilement aux parties du state
 */
export const chatSelectors = {
  // Obtenir le dernier message
  getLastMessage: () => {
    const messages = useChatStore.getState().messages
    return messages[messages.length - 1] || null
  },
  
  // Obtenir les messages par role
  getMessagesByRole: (role: 'user' | 'agent') => {
    return useChatStore.getState().messages.filter(msg => msg.role === role)
  },
  
  // Vérifier si le chat est vide
  isEmpty: () => {
    return useChatStore.getState().messages.length === 0
  },
  
  // Obtenir le nombre de messages
  getMessageCount: () => {
    return useChatStore.getState().messages.length
  },
} 