'use client'

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useChatStore } from "@/stores/chatStore"
import { Send } from "lucide-react"
import { FormEvent } from "react"

interface ChatInputProps {
  onSubmit: (message: string) => void
}

export function ChatInput({ onSubmit }: ChatInputProps) {
  const { input, isLoading, setInput } = useChatStore()

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    
    const trimmedInput = input.trim()
    if (trimmedInput && !isLoading) {
      onSubmit(trimmedInput)
      setInput('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const trimmedInput = input.trim()
      if (trimmedInput && !isLoading) {
        onSubmit(trimmedInput)
        setInput('')
      }
    }
  }

  const isDisabled = isLoading || !input.trim()

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-4 border-t">
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={isLoading ? "L'agent réfléchit..." : "Tapez votre message..."}
        disabled={isLoading}
        className="flex-1"
        autoComplete="off"
        autoFocus
      />
      <Button
        type="submit"
        disabled={isDisabled}
        size="icon"
        className="h-10 w-10 flex-shrink-0"
      >
        <Send className="h-4 w-4" />
        <span className="sr-only">Envoyer le message</span>
      </Button>
    </form>
  )
} 