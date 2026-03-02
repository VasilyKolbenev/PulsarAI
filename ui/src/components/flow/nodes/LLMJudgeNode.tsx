import { Handle, Position } from "@xyflow/react"

export function LLMJudgeNode({ data }: { data: Record<string, unknown> }) {
  const config = (data.config || {}) as Record<string, unknown>
  return (
    <div className="rounded-xl border-2 border-violet-500/30 bg-card px-4 py-3 shadow-lg min-w-[180px]">
      <Handle type="target" position={Position.Left} className="!bg-violet-500" />
      <div className="flex items-center gap-2 mb-2">
        <span className="w-6 h-6 rounded-md bg-violet-500/20 flex items-center justify-center text-violet-500 text-xs font-bold">⚖</span>
        <span className="text-xs font-semibold text-foreground">{String(data.label || "LLM Judge")}</span>
      </div>
      <div className="text-[10px] text-muted-foreground space-y-0.5">
        <div>Criteria: {String(config.criteria || "helpfulness,accuracy,safety")}</div>
        <div>Judge Model: {String(config.judge_model || "claude-sonnet-4-6")}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-violet-500" />
    </div>
  )
}
