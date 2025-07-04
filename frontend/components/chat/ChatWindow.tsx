'use client'

import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useChatStore } from "@/stores/chatStore"
import { MessageCircle, Wifi, WifiOff, AlertCircle, Loader2 } from "lucide-react"
import { ChatInput } from "./ChatInput"
import { MessageList } from "./MessageList"
import { useA2AClient, useTaskStreaming, useAgentCard } from "@/hooks/useA2AClient"
import { type StreamingEvent } from "@/lib/api"
import { useEffect } from "react"
import { toast } from "sonner"

export function ChatWindow() {
  const { 
    sendUserMessage, 
    setIsLoading, 
    setIsStreaming, 
    setError,
    setAgentCard,
    isLoading: storeIsLoading,
    isStreaming: storeIsStreaming,
    error: storeError,
    agentCard
  } = useChatStore()
  
  // Initialiser le client A2A
  const client = useA2AClient()
  
  // Hook pour récupérer la carte d'identité de l'agent
  const { 
    data: cardData, 
    loading: cardLoading, 
    error: cardError 
  } = useAgentCard(client)
  
  // Hook pour gérer le streaming des tâches
  const {
    isStreaming: hookIsStreaming,
    events: streamingEvents,
    error: streamingError,
    streamUserMessage
  } = useTaskStreaming(client, {
    onEvent: (event: StreamingEvent) => {
      console.log('Nouvel événement A2A:', event)
      // Traiter l'événement via le store Zustand
      useChatStore.getState().processStreamingEvent(event)
    },
    onError: (error: Error) => {
      console.error('Erreur de streaming A2A:', error)
      setError(`Erreur de streaming: ${error.message}`)
      setIsLoading(false)
      setIsStreaming(false)
      toast.error('Erreur lors du traitement de votre demande')
    },
    onEnd: () => {
      console.log('Streaming A2A terminé')
      setIsLoading(false)
      setIsStreaming(false)
      toast.success('Réponse reçue avec succès')
    }
  })

  // Mettre à jour la carte de l'agent dans le store
  useEffect(() => {
    if (cardData) {
      setAgentCard(cardData)
      console.log('Carte d\'agent chargée:', cardData)
    }
  }, [cardData, setAgentCard])

  // Gérer les erreurs de carte d'agent
  useEffect(() => {
    if (cardError) {
      console.error('Erreur lors du chargement de la carte agent:', cardError)
      const errorMessage = `Impossible de charger les informations de l'agent: ${cardError.message}`
      setError(errorMessage)
      toast.error('Problème de connexion avec l\'agent')
    }
  }, [cardError, setError])

  // Gérer les erreurs de streaming
  useEffect(() => {
    if (streamingError) {
      console.error('Erreur de streaming détectée:', streamingError)
      setError(`Erreur de communication: ${streamingError.message}`)
      toast.error('Problème avec le service de streaming')
    }
  }, [streamingError, setError])

  // Afficher les erreurs du store (uniquement si pas d'autres erreurs)
  useEffect(() => {
    if (storeError && !streamingError && !cardError) {
      toast.error(storeError)
    }
  }, [storeError, streamingError, cardError])

  // Synchroniser les états de streaming entre le hook et le store
  useEffect(() => {
    if (hookIsStreaming !== storeIsStreaming) {
      setIsStreaming(hookIsStreaming)
    }
  }, [hookIsStreaming, storeIsStreaming, setIsStreaming])

  // Afficher un message d'avertissement si le client n'est pas initialisé
  useEffect(() => {
    if (client === null) {
      // Attendre un moment pour laisser le temps au client de s'initialiser
      const timer = setTimeout(() => {
        if (client === null) {
          setError('Le client A2A n\'est pas encore initialisé. Vérifiez votre connexion.')
          console.warn('Client A2A non initialisé après délai d\'attente')
        }
      }, 5000)

      return () => clearTimeout(timer)
    } else {
      // Client initialisé, nettoyer les erreurs d'initialisation
      if (storeError && storeError.includes('client A2A')) {
        setError(null)
      }
    }
  }, [client, storeError, setError])

  // Fonction de soumission du message avec intégration A2A complète
  const handleSubmit = async (message: string) => {
    if (!client) {
      toast.error('Client A2A non initialisé')
      return
    }

    if (!message.trim()) {
      toast.error('Veuillez saisir un message')
      return
    }

    try {
      // 1. Créer et ajouter le message utilisateur via le store
      const userMessage = sendUserMessage(message.trim())
      console.log('Message utilisateur créé:', userMessage)

      // 2. Activer les états de chargement
      setIsLoading(true)
      setIsStreaming(true)
      setError(null)

      // 3. Envoyer le message avec streaming via notre client A2A
      console.log('Démarrage du streaming A2A...')
      await streamUserMessage(message.trim())

    } catch (error) {
      console.error('Erreur lors de l\'envoi du message:', error)
      setIsLoading(false)
      setIsStreaming(false)
      
      const errorMessage = error instanceof Error ? error.message : 'Erreur inconnue'
      setError(`Échec de l'envoi: ${errorMessage}`)
      toast.error('Impossible d\'envoyer votre message')
    }
  }

  // Fonctions utilitaires pour l'affichage
  const isConnected = !streamingError && !cardError && client !== null
  const hasActiveStream = hookIsStreaming || storeIsStreaming
  const hasErrors = !!(storeError || streamingError || cardError)

  const getConnectionStatus = () => {
    if (hasErrors) return { status: 'error', label: 'Erreur', color: 'text-red-500' }
    if (hasActiveStream) return { status: 'streaming', label: 'Streaming', color: 'text-green-500' }
    if (isConnected) return { status: 'connected', label: 'En ligne', color: 'text-green-500' }
    return { status: 'disconnected', label: 'Hors ligne', color: 'text-yellow-500' }
  }

  const getConnectionIcon = () => {
    const status = getConnectionStatus()
    switch (status.status) {
      case 'error':
        return <WifiOff className="h-4 w-4 text-red-500" />
      case 'streaming':
        return <Wifi className="h-4 w-4 text-green-500 animate-pulse" />
      case 'connected':
        return <Wifi className="h-4 w-4 text-green-500" />
      default:
        return <WifiOff className="h-4 w-4 text-yellow-500" />
    }
  }

  const getTitle = () => {
    if (agentCard) {
      return agentCard.name
    }
    if (cardLoading) {
      return "Chargement de l'agent..."
    }
    return "Assistant d'Inclusion Sociale"
  }

  const getSubtitle = () => {
    if (agentCard?.description) {
      return agentCard.description
    }
    return "Assistant IA pour l'accompagnement social"
  }

  // État de débogage pour diagnostiquer les problèmes
  const debugInfo = {
    clientAvailable: !!client,
    windowAvailable: typeof window !== 'undefined',
    fetchAvailable: typeof fetch !== 'undefined',
    environment: process.env.NODE_ENV,
  }

  return (
    <Card className="h-[600px] w-full max-w-4xl mx-auto flex flex-col">
      <CardHeader className="flex flex-row items-center space-y-0 pb-4">
        <div className="flex items-center gap-2 flex-1">
          <MessageCircle className="h-5 w-5 text-blue-500" />
          <div className="flex flex-col">
            <CardTitle className="text-lg font-semibold">
              {getTitle()}
              {agentCard && (
                <span className="text-xs text-muted-foreground ml-2 font-normal">
                  v{agentCard.version}
                </span>
              )}
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              {getSubtitle()}
            </p>
            {/* Debug info temporaire */}
            {process.env.NODE_ENV === 'development' && (
              <div className="text-xs text-muted-foreground mt-1 font-mono">
                Debug: Client={debugInfo.clientAvailable ? '✓' : '✗'} | 
                Window={debugInfo.windowAvailable ? '✓' : '✗'} | 
                Fetch={debugInfo.fetchAvailable ? '✓' : '✗'} | 
                Env={debugInfo.environment}
              </div>
            )}
          </div>
          {cardLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
          )}
        </div>
        
        {/* Indicateurs de statut améliorés */}
        <div className="flex items-center gap-3">
          {/* Indicateur d'erreur */}
          {hasErrors && (
            <div 
              className="flex items-center gap-1 text-red-500 cursor-help" 
              title={storeError || streamingError?.message || cardError?.message}
            >
              <AlertCircle className="h-4 w-4" />
              <span className="text-xs font-medium">Erreur</span>
            </div>
          )}
          
          {/* Indicateur de streaming */}
          {hasActiveStream && (
            <div className="flex items-center gap-1 text-blue-500">
              <div className="h-2 w-2 bg-blue-500 rounded-full animate-pulse" />
              <span className="text-xs font-medium">Streaming</span>
            </div>
          )}

          {/* Indicateur de chargement */}
          {storeIsLoading && !hasActiveStream && (
            <div className="flex items-center gap-1 text-orange-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span className="text-xs font-medium">Traitement</span>
            </div>
          )}
          
          {/* Statut de connexion */}
          <div 
            className="flex items-center gap-1 cursor-help" 
            title={`Statut: ${getConnectionStatus().label}${hasErrors ? ` - ${storeError || streamingError?.message || cardError?.message}` : ''}`}
          >
            {getConnectionIcon()}
            <span className={`text-xs font-medium ${getConnectionStatus().color}`}>
              {getConnectionStatus().label}
            </span>
          </div>

          {/* Nombre d'événements de streaming */}
          {streamingEvents.length > 0 && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <span className="text-xs">
                {streamingEvents.length} événements
              </span>
            </div>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="flex-1 flex flex-col p-0 overflow-hidden">
        <MessageList />
      </CardContent>
      
      <CardFooter className="p-0">
        <ChatInput 
          onSubmit={handleSubmit} 
          disabled={!isConnected || hasActiveStream || storeIsLoading}
        />
      </CardFooter>
    </Card>
  )
} 