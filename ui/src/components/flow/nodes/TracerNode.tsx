import { Handle, Position } from "@xyflow/react"

export function TracerNode({ data }: { data: Record<string, unknown> }) {
  const config = (data.config || {}) as Record<string, unknown>
  return (
    <div className="rounded-xl border-2 border-indigo-500/30 bg-card px-4 py-3 shadow-lg min-w-[180px]">
      <Handle type="target" position={Position.Left} className="!bg-indigo-500" />
      <div className="flex items-center gap-2 mb-2">
        <span className="w-6 h-6 rounded-md bg-indigo-500/20 flex items-center justify-center text-indigo-500 text-xs font-bold">📊</span>
        <span className="text-xs font-semibold text-foreground">{String(data.label || "Tracer")}</span>
      </div>
      <div className="text-[10px] text-muted-foreground space-y-0.5">
        <div>Backend: {String(config.backend || "local")}</div>
        <div>Cost Tracking: {config.cost_tracking !== false ? "on" : "off"}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-indigo-500" />
    </div>
  )
}
