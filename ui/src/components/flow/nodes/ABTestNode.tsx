import { Handle, Position } from "@xyflow/react"

export function ABTestNode({ data }: { data: Record<string, unknown> }) {
  const config = (data.config || {}) as Record<string, unknown>
  return (
    <div className="rounded-xl border-2 border-pink-500/30 bg-card px-4 py-3 shadow-lg min-w-[180px]">
      <Handle type="target" position={Position.Left} id="model_a" className="!bg-pink-500" style={{ top: "35%" }} />
      <Handle type="target" position={Position.Left} id="model_b" className="!bg-pink-400" style={{ top: "65%" }} />
      <div className="flex items-center gap-2 mb-2">
        <span className="w-6 h-6 rounded-md bg-pink-500/20 flex items-center justify-center text-pink-500 text-xs font-bold">AB</span>
        <span className="text-xs font-semibold text-foreground">{String(data.label || "A/B Test")}</span>
      </div>
      <div className="text-[10px] text-muted-foreground space-y-0.5">
        <div>Metric: {String(config.metric || "latency_ms")}</div>
        <div>Min Samples: {String(config.min_samples || "100")}</div>
        <div>Split: {String(config.traffic_split || "50/50")}</div>
      </div>
      <Handle type="source" position={Position.Right} id="winner" className="!bg-pink-500" />
    </div>
  )
}
