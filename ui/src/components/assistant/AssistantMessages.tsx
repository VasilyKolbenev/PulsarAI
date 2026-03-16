import type { AssistantMessage } from "@/hooks/useAssistant"
import { Bot, User } from "lucide-react"

interface Props {
  messages: AssistantMessage[]
  isLoading: boolean
}

export function AssistantMessages({ messages, isLoading }: Props) {
  return (
    <div className="space-y-3">
      {messages.length === 0 && (
        <div className="text-center py-8 text-muted-foreground text-xs">
          <Bot className="mx-auto mb-2 opacity-50" size={24} />
          <p>Pulsar Co-pilot ready.</p>
          <p className="mt-1">Try <code className="text-primary">/help</code> or ask a question.</p>
        </div>
      )}

      {messages.map((msg) => (
        <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
          {msg.role === "assistant" && (
            <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0 mt-0.5">
              <Bot size={12} className="text-primary" />
            </div>
          )}

          <div
            className={`max-w-[85%] px-3 py-2 rounded-lg text-xs leading-relaxed ${
              msg.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/80"
            }`}
          >
            <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
            {msg.mode && (
              <div className="mt-1 opacity-50 text-[10px]">
                {msg.mode === "llm" ? "AI" : "cmd"}
              </div>
            )}
          </div>

          {msg.role === "user" && (
            <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center shrink-0 mt-0.5">
              <User size={12} className="text-muted-foreground" />
            </div>
          )}
        </div>
      ))}

      {isLoading && (
        <div className="flex gap-2">
          <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
            <Bot size={12} className="text-primary" />
          </div>
          <div className="bg-secondary/80 px-3 py-2 rounded-lg text-xs text-muted-foreground">
            <span className="inline-flex gap-1">
              <span className="animate-bounce" style={{ animationDelay: "0ms" }}>.</span>
              <span className="animate-bounce" style={{ animationDelay: "150ms" }}>.</span>
              <span className="animate-bounce" style={{ animationDelay: "300ms" }}>.</span>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
