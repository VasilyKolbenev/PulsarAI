import { useState, useRef, useEffect } from "react"
import { cn } from "@/lib/utils"
import { ChevronDown, Search, Cpu, Eye, Code2 } from "lucide-react"

type ModelCategory = "llm" | "vlm" | "code"

interface ModelEntry {
  id: string
  label: string
  size: string
  category: ModelCategory
}

const RECOMMENDED_MODELS: ModelEntry[] = [
  // Text LLM
  { id: "Qwen/Qwen2.5-3B-Instruct", label: "Qwen 2.5 3B Instruct", size: "3B", category: "llm" },
  { id: "Qwen/Qwen2.5-1.5B-Instruct", label: "Qwen 2.5 1.5B Instruct", size: "1.5B", category: "llm" },
  { id: "Qwen/Qwen2.5-7B-Instruct", label: "Qwen 2.5 7B Instruct", size: "7B", category: "llm" },
  { id: "meta-llama/Llama-3.2-1B-Instruct", label: "Llama 3.2 1B Instruct", size: "1B", category: "llm" },
  { id: "meta-llama/Llama-3.2-3B-Instruct", label: "Llama 3.2 3B Instruct", size: "3B", category: "llm" },
  { id: "mistralai/Mistral-7B-Instruct-v0.3", label: "Mistral 7B Instruct v0.3", size: "7B", category: "llm" },
  { id: "google/gemma-2-2b-it", label: "Gemma 2 2B IT", size: "2B", category: "llm" },
  { id: "google/gemma-2-9b-it", label: "Gemma 2 9B IT", size: "9B", category: "llm" },
  { id: "microsoft/Phi-3-mini-4k-instruct", label: "Phi-3 Mini 4K", size: "3.8B", category: "llm" },
  { id: "microsoft/Phi-3.5-mini-instruct", label: "Phi-3.5 Mini", size: "3.8B", category: "llm" },
  { id: "TinyLlama/TinyLlama-1.1B-Chat-v1.0", label: "TinyLlama 1.1B Chat", size: "1.1B", category: "llm" },
  // Vision LLM
  { id: "Qwen/Qwen2.5-VL-3B-Instruct", label: "Qwen 2.5 VL 3B", size: "3B", category: "vlm" },
  { id: "Qwen/Qwen2.5-VL-7B-Instruct", label: "Qwen 2.5 VL 7B", size: "7B", category: "vlm" },
  // Code
  { id: "Qwen/Qwen2.5-Coder-3B-Instruct", label: "Qwen 2.5 Coder 3B", size: "3B", category: "code" },
  { id: "Qwen/Qwen2.5-Coder-7B-Instruct", label: "Qwen 2.5 Coder 7B", size: "7B", category: "code" },
  { id: "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct", label: "DeepSeek Coder V2 Lite", size: "16B", category: "code" },
]

const CATEGORY_META: Record<ModelCategory, { label: string; icon: React.ElementType; color: string }> = {
  llm: { label: "Text LLM", icon: Cpu, color: "text-primary" },
  vlm: { label: "Vision LLM", icon: Eye, color: "text-amber-400" },
  code: { label: "Code", icon: Code2, color: "text-emerald-400" },
}

interface ModelSelectorProps {
  value: string
  onChange: (value: string) => void
  className?: string
}

export function ModelSelector({ value, onChange, className }: ModelSelectorProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const lowerQuery = query.toLowerCase()
  const filtered = RECOMMENDED_MODELS.filter(
    (m) =>
      m.id.toLowerCase().includes(lowerQuery) ||
      m.label.toLowerCase().includes(lowerQuery) ||
      m.category.includes(lowerQuery),
  )

  // Group by category
  const grouped = new Map<ModelCategory, ModelEntry[]>()
  for (const m of filtered) {
    const list = grouped.get(m.category) ?? []
    list.push(m)
    grouped.set(m.category, list)
  }

  // Check if query looks like a custom HF model ID
  const isCustomId = query.includes("/") && !filtered.some((m) => m.id === query)

  const handleSelect = (id: string) => {
    onChange(id)
    setQuery("")
    setOpen(false)
  }

  // Display value
  const selectedModel = RECOMMENDED_MODELS.find((m) => m.id === value)
  const displayLabel = selectedModel ? selectedModel.label : value

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Trigger / Input */}
      <div
        className={cn(
          "flex items-center gap-2 w-full bg-input border rounded-md px-3 py-2 text-sm cursor-pointer",
          open ? "border-ring ring-2 ring-ring" : "border-border",
        )}
        onClick={() => {
          setOpen(true)
          setTimeout(() => inputRef.current?.focus(), 0)
        }}
      >
        {selectedModel && (
          <CategoryBadge category={selectedModel.category} size={selectedModel.size} />
        )}
        {open ? (
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && isCustomId) {
                handleSelect(query)
              }
              if (e.key === "Escape") {
                setOpen(false)
                setQuery("")
              }
            }}
            placeholder="Search models or paste HuggingFace ID..."
            className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="flex-1 truncate">{displayLabel}</span>
        )}
        <ChevronDown
          size={16}
          className={cn(
            "shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </div>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-card border border-border rounded-md shadow-lg max-h-72 overflow-y-auto">
          {filtered.length === 0 && !isCustomId && (
            <div className="px-3 py-6 text-center text-sm text-muted-foreground">
              No models found. Paste a HuggingFace model ID (org/model).
            </div>
          )}

          {/* Custom HF ID option */}
          {isCustomId && (
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-secondary text-left border-b border-border"
              onClick={() => handleSelect(query)}
            >
              <Search size={14} className="text-primary shrink-0" />
              <span className="text-primary font-medium">Use:</span>
              <span className="font-mono truncate">{query}</span>
            </button>
          )}

          {/* Grouped models */}
          {(["llm", "vlm", "code"] as ModelCategory[]).map((cat) => {
            const models = grouped.get(cat)
            if (!models?.length) return null
            const meta = CATEGORY_META[cat]
            const Icon = meta.icon

            return (
              <div key={cat}>
                <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider bg-secondary/50">
                  <Icon size={12} className={meta.color} />
                  {meta.label}
                </div>
                {models.map((m) => (
                  <button
                    key={m.id}
                    className={cn(
                      "w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-secondary transition-colors",
                      m.id === value && "bg-primary/10 text-primary",
                    )}
                    onClick={() => handleSelect(m.id)}
                  >
                    <span className="flex-1 truncate">{m.label}</span>
                    <span className="text-[10px] font-mono text-muted-foreground bg-secondary rounded px-1.5 py-0.5">
                      {m.size}
                    </span>
                    <span className="text-[10px] text-muted-foreground truncate max-w-[160px] font-mono opacity-60">
                      {m.id.split("/")[0]}
                    </span>
                  </button>
                ))}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function CategoryBadge({ category, size }: { category: ModelCategory; size: string }) {
  const meta = CATEGORY_META[category]
  const Icon = meta.icon
  return (
    <div className="flex items-center gap-1 shrink-0">
      <Icon size={14} className={meta.color} />
      <span className="text-[10px] font-mono text-muted-foreground bg-secondary rounded px-1 py-0.5">
        {size}
      </span>
    </div>
  )
}
