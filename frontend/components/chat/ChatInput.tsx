'use client'

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useChatStore } from "@/stores/chatStore"
import { Send, Loader2 } from "lucide-react"
import { FormEvent } from "react"

interface ChatInputProps {
  onSubmit: (message: string) => void
  disabled?: boolean
}

export function ChatInput({ onSubmit, disabled = false }: ChatInputProps) {
  const { input, isLoading, isStreaming, setInput } = useChatStore()

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    
    const trimmedInput = input.trim()
    if (trimmedInput && !isLoading && !disabled && !isStreaming) {
      onSubmit(trimmedInput)
      setInput('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const trimmedInput = input.trim()
      if (trimmedInput && !isLoading && !disabled && !isStreaming) {
        onSubmit(trimmedInput)
        setInput('')
      }
    }
  }

  const isInputDisabled = isLoading || disabled || isStreaming
  const isButtonDisabled = isInputDisabled || !input.trim()

  const getPlaceholder = () => {
    if (disabled) return "Connexion en cours..."
    if (isStreaming) return "Streaming en cours..."
    if (isLoading) return "L'agent réfléchit..."
    return "Tapez votre message..."
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-4 border-t">
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={getPlaceholder()}
        disabled={isInputDisabled}
        className="flex-1"
        autoComplete="off"
        autoFocus={!isInputDisabled}
      />
      <Button
        type="submit"
        disabled={isButtonDisabled}
        size="icon"
        className="h-10 w-10 flex-shrink-0"
      >
        {isLoading || isStreaming ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
        <span className="sr-only">
          {isButtonDisabled ? "Envoi désactivé" : "Envoyer le message"}
        </span>
      </Button>
    </form>
  )
} 