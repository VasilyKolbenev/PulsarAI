import { Handle, Position } from "@xyflow/react"

export function CanaryNode({ data }: { data: Record<string, unknown> }) {
  const config = (data.config || {}) as Record<string, unknown>
  return (
    <div className="rounded-xl border-2 border-emerald-500/30 bg-card px-4 py-3 shadow-lg min-w-[180px]">
      <Handle type="target" position={Position.Left} id="primary" className="!bg-emerald-500" style={{ top: "35%" }} />
      <Handle type="target" position={Position.Left} id="canary" className="!bg-emerald-400" style={{ top: "65%" }} />
      <div className="flex items-center gap-2 mb-2">
        <span className="w-6 h-6 rounded-md bg-emerald-500/20 flex items-center justify-center text-emerald-500 text-xs font-bold">🐤</span>
        <span className="text-xs font-semibold text-foreground">{String(data.label || "Canary Deploy")}</span>
      </div>
      <div className="text-[10px] text-muted-foreground space-y-0.5">
        <div>Canary Weight: {String(config.canary_weight || "10")}%</div>
        <div>Error Threshold: {String(config.error_threshold || "5")}%</div>
        <div>Auto Rollback: {config.auto_rollback !== false ? "on" : "off"}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-emerald-500" />
    </div>
  )
}
