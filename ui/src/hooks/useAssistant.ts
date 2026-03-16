import { useState, useCallback, useEffect, useRef } from "react"
import { useLocation } from "react-router-dom"
import { api } from "@/api/client"

export interface AssistantMessage {
  id: string
  role: "user" | "assistant"
  content: string
  mode?: "command" | "llm"
  actions?: Array<Record<string, unknown>>
  timestamp: number
}

interface PlatformStatus {
  active_jobs: Array<Record<string, unknown>>
  recent_experiments: Array<Record<string, unknown>>
  llm_available: boolean
}

const SESSION_KEY = "pulsar_assistant_session"
const POLL_INTERVAL = 10_000

export function useAssistant() {
  const [messages, setMessages] = useState<AssistantMessage[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<PlatformStatus | null>(null)
  const [notifications, setNotifications] = useState(0)
  const sessionRef = useRef(localStorage.getItem(SESSION_KEY) || "")
  const prevJobsRef = useRef<string[]>([])
  const location = useLocation()

  // Persist session ID
  const setSession = useCallback((id: string) => {
    sessionRef.current = id
    localStorage.setItem(SESSION_KEY, id)
  }, [])

  // Poll platform status
  useEffect(() => {
    const poll = async () => {
      try {
        const s = await api.assistantStatus()
        setStatus(s)

        // Detect newly completed jobs
        const currentRunning = s.active_jobs.map((j) => String(j.job_id))
        const previousRunning = prevJobsRef.current
        const finished = previousRunning.filter((id) => !currentRunning.includes(id))
        if (finished.length > 0 && !isOpen) {
          setNotifications((n) => n + finished.length)
        }
        prevJobsRef.current = currentRunning
      } catch {
        // server not available
      }
    }

    poll()
    const interval = setInterval(poll, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [isOpen])

  const send = useCallback(async (text: string) => {
    if (!text.trim()) return

    const userMsg: AssistantMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      const res = await api.assistantChat({
        message: text,
        session_id: sessionRef.current || undefined,
        context: {
          page: location.pathname,
          active_jobs: status?.active_jobs || [],
        },
      })

      setSession(res.session_id)

      const assistantMsg: AssistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.answer,
        mode: res.mode as "command" | "llm",
        actions: res.actions,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (e) {
      const errorMsg: AssistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Connection error: ${e instanceof Error ? e.message : "Unknown"}`,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }, [location.pathname, status])

  const toggle = useCallback(() => {
    setIsOpen((prev) => !prev)
    setNotifications(0)
  }, [])

  return {
    messages,
    send,
    isOpen,
    toggle,
    isLoading,
    status,
    notifications,
  }
}
