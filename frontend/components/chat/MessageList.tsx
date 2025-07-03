'use client'

import { ScrollArea } from "@/components/ui/scroll-area"
import { useChatStore } from "@/stores/chatStore"
import { ChatMessage } from "./ChatMessage"
import { useEffect, useRef } from "react"

export function MessageList() {
  const messages = useChatStore((state) => state.messages)
  const scrollAreaRef = useRef<HTMLDivElement>(null)

  // Défilement automatique vers le bas lorsque de nouveaux messages sont ajoutés
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight
      }
    }
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <p className="text-lg font-medium">Commencez une conversation</p>
          <p className="text-sm text-gray-400 mt-1">
            Posez votre première question pour démarrer
          </p>
        </div>
      </div>
    )
  }

  return (
    <ScrollArea className="flex-1 px-4" ref={scrollAreaRef}>
      <div className="py-4 space-y-4">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
      </div>
    </ScrollArea>
  )
} 