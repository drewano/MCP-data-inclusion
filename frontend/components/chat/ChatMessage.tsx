import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Card, CardContent } from "@/components/ui/card"
import { ChatMessage as ChatMessageType } from "@/stores/chatStore"
import { Bot, User } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { cn } from "@/lib/utils"

interface ChatMessageProps {
  message: ChatMessageType
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user"
  
  return (
    <div
      className={cn(
        "flex w-full gap-3 mb-4",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <Avatar className="h-8 w-8 flex-shrink-0">
          <AvatarImage src="/agent-avatar.png" alt="Agent" />
          <AvatarFallback className="bg-blue-500 text-white">
            <Bot className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      )}
      
      <Card
        className={cn(
          "max-w-[80%] break-words",
          isUser
            ? "bg-blue-500 text-white border-blue-500"
            : "bg-gray-50 border-gray-200"
        )}
      >
        <CardContent className="p-3">
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-sm max-w-none prose-p:leading-relaxed prose-pre:p-0">
              <ReactMarkdown
                components={{
                  p: ({ children }) => (
                    <p className="text-sm leading-relaxed mb-2 last:mb-0">
                      {children}
                    </p>
                  ),
                  code: ({ children, className }) => {
                    const isInline = !className
                    return isInline ? (
                      <code className="bg-gray-200 px-1 py-0.5 rounded text-xs font-mono">
                        {children}
                      </code>
                    ) : (
                      <pre className="bg-gray-800 text-white p-3 rounded-md text-xs overflow-x-auto">
                        <code>{children}</code>
                      </pre>
                    )
                  },
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside text-sm space-y-1 mb-2">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-inside text-sm space-y-1 mb-2">
                      {children}
                    </ol>
                  ),
                  h1: ({ children }) => (
                    <h1 className="text-lg font-bold mb-2">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-base font-semibold mb-2">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-sm font-semibold mb-1">{children}</h3>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </CardContent>
      </Card>
      
      {isUser && (
        <Avatar className="h-8 w-8 flex-shrink-0">
          <AvatarImage src="/user-avatar.png" alt="User" />
          <AvatarFallback className="bg-green-500 text-white">
            <User className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  )
} 