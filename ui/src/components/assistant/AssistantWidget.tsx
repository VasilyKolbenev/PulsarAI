import { useState, useRef, useEffect } from "react"
import { Bot, X, Send, Zap } from "lucide-react"
import { useAssistant } from "@/hooks/useAssistant"
import { AssistantMessages } from "./AssistantMessages"

const QUICK_ACTIONS = [
  { label: "Status", cmd: "/status" },
  { label: "Datasets", cmd: "/datasets" },
  { label: "Workflows", cmd: "/workflows" },
  { label: "Recommend", cmd: "/recommend" },
  { label: "Hardware", cmd: "/hardware" },
]

export function AssistantWidget() {
  const {
    messages,
    send,
    isOpen,
    toggle,
    isLoading,
    status,
    notifications,
  } = useAssistant()

  const [input, setInput] = useState("")
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen) {
      endRef.current?.scrollIntoView({ behavior: "smooth" })
      inputRef.current?.focus()
    }
  }, [messages, isOpen])

  const handleSend = () => {
    if (!input.trim() || isLoading) return
    send(input.trim())
    setInput("")
  }

  const handleQuickAction = (cmd: string) => {
    send(cmd)
  }

  // Collapsed: floating button
  if (!isOpen) {
    return (
      <button
        onClick={toggle}
        className="fixed bottom-6 right-6 w-12 h-12 bg-primary text-primary-foreground rounded-full shadow-lg shadow-primary/25 flex items-center justify-center hover:bg-primary/90 transition-all hover:scale-105 z-50"
        title="Pulsar Co-pilot"
      >
        <Bot size={22} />
        {notifications > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {notifications}
          </span>
        )}
      </button>
    )
  }

  // Expanded: sliding panel
  return (
    <div className="fixed bottom-6 right-6 w-96 h-[32rem] bg-card border border-border rounded-xl shadow-2xl shadow-black/40 flex flex-col z-50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-primary/20 flex items-center justify-center">
            <Bot size={14} className="text-primary" />
          </div>
          <div>
            <div className="text-sm font-semibold">Pulsar Co-pilot</div>
            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
              {status?.llm_available ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-success inline-block" />
                  AI mode
                </>
              ) : (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-warning inline-block" />
                  Command mode
                </>
              )}
              {(status?.active_jobs?.length ?? 0) > 0 && (
                <span className="ml-2 text-warning">
                  {status!.active_jobs.length} job running
                </span>
              )}
            </div>
          </div>
        </div>
        <button onClick={toggle} className="text-muted-foreground hover:text-foreground p-1">
          <X size={16} />
        </button>
      </div>

      {/* Quick actions */}
      <div className="flex gap-1.5 px-3 py-2 border-b border-border overflow-x-auto">
        {QUICK_ACTIONS.map(({ label, cmd }) => (
          <button
            key={cmd}
            onClick={() => handleQuickAction(cmd)}
            disabled={isLoading}
            className="flex items-center gap-1 px-2 py-1 bg-secondary/80 hover:bg-secondary text-xs rounded-md whitespace-nowrap transition-colors disabled:opacity-50"
          >
            <Zap size={10} className="text-primary" />
            {label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3">
        <AssistantMessages messages={messages} isLoading={isLoading} />
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="px-3 py-2 border-t border-border">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="/help or ask a question..."
            disabled={isLoading}
            className="flex-1 bg-input border border-border rounded-md px-3 py-1.5 text-xs focus:ring-1 focus:ring-ring focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="px-2.5 py-1.5 bg-primary text-primary-foreground rounded-md disabled:opacity-50 transition-colors hover:bg-primary/90"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
