import { useCallback, useSyncExternalStore } from "react"

export type ToastVariant = "success" | "error" | "warning" | "info"

export interface Toast {
  id: string
  message: string
  variant: ToastVariant
  duration: number
}

type Listener = () => void

let toasts: Toast[] = []
const listeners = new Set<Listener>()
let nextId = 0

function emitChange() {
  for (const fn of listeners) fn()
}

function getSnapshot(): Toast[] {
  return toasts
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function addToast(
  message: string,
  variant: ToastVariant = "info",
  duration = 4000,
) {
  const id = String(++nextId)
  toasts = [...toasts, { id, message, variant, duration }]
  emitChange()
  if (duration > 0) {
    setTimeout(() => dismissToast(id), duration)
  }
}

export function dismissToast(id: string) {
  toasts = toasts.filter((t) => t.id !== id)
  emitChange()
}

export function useToast() {
  const items = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info", duration = 4000) =>
      addToast(message, variant, duration),
    [],
  )

  const success = useCallback(
    (message: string) => addToast(message, "success"),
    [],
  )
  const error = useCallback(
    (message: string) => addToast(message, "error", 6000),
    [],
  )
  const warning = useCallback(
    (message: string) => addToast(message, "warning"),
    [],
  )
  const info = useCallback(
    (message: string) => addToast(message, "info"),
    [],
  )

  return { toasts: items, toast, success, error, warning, info, dismiss: dismissToast }
}
