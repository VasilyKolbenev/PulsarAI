import { Handle, Position } from "@xyflow/react"

export function CacheNode({ data }: { data: Record<string, unknown> }) {
  const config = (data.config || {}) as Record<string, unknown>
  return (
    <div className="rounded-xl border-2 border-amber-500/30 bg-card px-4 py-3 shadow-lg min-w-[180px]">
      <Handle type="target" position={Position.Left} className="!bg-amber-500" />
      <div className="flex items-center gap-2 mb-2">
        <span className="w-6 h-6 rounded-md bg-amber-500/20 flex items-center justify-center text-amber-500 text-xs font-bold">⚡</span>
        <span className="text-xs font-semibold text-foreground">{String(data.label || "Cache")}</span>
      </div>
      <div className="text-[10px] text-muted-foreground space-y-0.5">
        <div>TTL: {String(config.ttl || "3600")}s</div>
        <div>Max Entries: {String(config.max_entries || "10000")}</div>
        <div>Strategy: {String(config.strategy || "exact")}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-amber-500" />
    </div>
  )
}
