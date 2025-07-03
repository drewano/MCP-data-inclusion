'use client'

import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useChatStore } from "@/stores/chatStore"
import { MessageCircle, Wifi, WifiOff, AlertCircle } from "lucide-react"
import { ChatInput } from "./ChatInput"
import { MessageList } from "./MessageList"
import { useA2AClient, useTaskStreaming, useAgentCard } from "@/hooks/useA2AClient"
import { useEffect } from "react"
import { toast } from "sonner"

export function ChatWindow() {
  const { 
    sendUserMessage, 
    setIsLoading, 
    setIsStreaming, 
    setError,
    setAgentCard,
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
    error: streamingError,
    streamUserMessage
  } = useTaskStreaming(client, {
    onEvent: (event: import('@/lib/api').StreamingEvent) => {
      console.log('Nouvel événement:', event)
      // Le processStreamingEvent du store va gérer la mise à jour de l'état
      // On peut l'appeler ici si on veut
    },
    onError: (error: Error) => {
      console.error('Erreur de streaming:', error)
      setError(`Erreur: ${error.message}`)
      setIsLoading(false)
      setIsStreaming(false)
      toast.error('Erreur lors du traitement de votre demande')
    },
    onEnd: () => {
      console.log('Streaming terminé')
      setIsLoading(false)
      setIsStreaming(false)
    }
  })

  // Mettre à jour la carte de l'agent dans le store
  useEffect(() => {
    if (cardData) {
      setAgentCard(cardData)
    }
    if (cardError) {
      console.error('Erreur lors du chargement de la carte agent:', cardError)
      toast.error('Impossible de charger les informations de l\'agent')
    }
  }, [cardData, cardError, setAgentCard])

  // Afficher les erreurs de streaming
  useEffect(() => {
    if (streamingError) {
      setError(`Erreur de streaming: ${streamingError.message}`)
      toast.error('Problème avec le service de streaming')
    }
  }, [streamingError, setError])

  // Fonction de soumission du message avec intégration A2A
  const handleSubmit = async (message: string) => {
    try {
      // Créer et ajouter le message utilisateur avec intégration A2A
      sendUserMessage(message)

      // Activer les états de chargement
      setIsLoading(true)
      setIsStreaming(true)
      setError(null)

      // Envoyer le message avec streaming via notre client A2A
      await streamUserMessage(message)

    } catch (error) {
      console.error('Erreur lors de l\'envoi du message:', error)
      setIsLoading(false)
      setIsStreaming(false)
      
      const errorMessage = error instanceof Error ? error.message : 'Erreur inconnue'
      setError(`Erreur: ${errorMessage}`)
      toast.error('Impossible d\'envoyer votre message')
    }
  }

  // Fonction pour obtenir l'icône de statut de connexion
  const getConnectionIcon = () => {
    if (streamingError) {
      return <WifiOff className="h-4 w-4 text-red-500" />
    }
    if (hookIsStreaming || storeIsStreaming) {
      return <Wifi className="h-4 w-4 text-green-500" />
    }
    return <Wifi className="h-4 w-4 text-yellow-500" />
  }

  // Fonction pour obtenir le titre avec informations de l'agent
  const getTitle = () => {
    if (agentCard) {
      return agentCard.name
    }
    if (cardLoading) {
      return "Chargement..."
    }
    return "Assistant d'Inclusion Sociale"
  }

  return (
    <Card className="h-[600px] w-full max-w-4xl mx-auto flex flex-col">
      <CardHeader className="flex flex-row items-center space-y-0 pb-4">
        <div className="flex items-center gap-2 flex-1">
          <MessageCircle className="h-5 w-5 text-blue-500" />
          <CardTitle className="text-lg font-semibold">
            {getTitle()}
          </CardTitle>
          {agentCard && (
            <span className="text-xs text-muted-foreground">
              v{agentCard.version}
            </span>
          )}
        </div>
        
                 {/* Indicateurs de statut */}
         <div className="flex items-center gap-2">
           {(storeError || streamingError) && (
             <div className="flex items-center gap-1 text-red-500" title={storeError || streamingError?.message}>
               <AlertCircle className="h-4 w-4" />
               <span className="text-xs">Erreur</span>
             </div>
           )}
           
           {(hookIsStreaming || storeIsStreaming) && (
             <div className="flex items-center gap-1 text-blue-500">
               <div className="h-2 w-2 bg-blue-500 rounded-full animate-pulse" />
               <span className="text-xs">Streaming</span>
             </div>
           )}
           
           <div className="flex items-center gap-1" title={streamingError ? 'Déconnecté' : 'En ligne'}>
             {getConnectionIcon()}
             <span className="text-xs text-muted-foreground">
               {streamingError ? 'Hors ligne' : 'En ligne'}
             </span>
           </div>
         </div>
      </CardHeader>
      
      <CardContent className="flex-1 flex flex-col p-0 overflow-hidden">
        <MessageList />
      </CardContent>
      
      <CardFooter className="p-0">
        <ChatInput onSubmit={handleSubmit} />
      </CardFooter>
    </Card>
  )
} 