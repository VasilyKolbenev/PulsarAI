import { Handle, Position } from "@xyflow/react"

export function FeedbackNode({ data }: { data: Record<string, unknown> }) {
  const config = (data.config || {}) as Record<string, unknown>
  return (
    <div className="rounded-xl border-2 border-sky-500/30 bg-card px-4 py-3 shadow-lg min-w-[180px]">
      <Handle type="target" position={Position.Left} className="!bg-sky-500" />
      <div className="flex items-center gap-2 mb-2">
        <span className="w-6 h-6 rounded-md bg-sky-500/20 flex items-center justify-center text-sky-500 text-xs font-bold">👍</span>
        <span className="text-xs font-semibold text-foreground">{String(data.label || "Human Feedback")}</span>
      </div>
      <div className="text-[10px] text-muted-foreground space-y-0.5">
        <div>Type: {String(config.feedback_type || "thumbs")}</div>
        <div>Export: {String(config.export_format || "dpo")}</div>
      </div>
      <Handle type="source" position={Position.Right} id="dpo_data" className="!bg-sky-500" />
    </div>
  )
}
