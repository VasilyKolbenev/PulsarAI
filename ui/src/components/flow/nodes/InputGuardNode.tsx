import { Handle, Position } from "@xyflow/react"

export function InputGuardNode({ data }: { data: Record<string, unknown> }) {
  const config = (data.config || {}) as Record<string, unknown>
  const rules = String(config.rules || "pii,injection,toxicity")
  return (
    <div className="rounded-xl border-2 border-red-500/30 bg-card px-4 py-3 shadow-lg min-w-[180px]">
      <Handle type="target" position={Position.Left} className="!bg-red-500" />
      <div className="flex items-center gap-2 mb-2">
        <span className="w-6 h-6 rounded-md bg-red-500/20 flex items-center justify-center text-red-500 text-xs font-bold">🛡</span>
        <span className="text-xs font-semibold text-foreground">{String(data.label || "Input Guard")}</span>
      </div>
      <div className="text-[10px] text-muted-foreground space-y-0.5">
        <div>Rules: {rules}</div>
        <div>Action: {String(config.action || "block")}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-red-500" />
    </div>
  )
}
