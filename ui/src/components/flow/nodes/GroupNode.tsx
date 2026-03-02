import { Handle, Position } from "@xyflow/react"

export function GroupNode({ data }: { data: Record<string, unknown> }) {
  const config = (data.config || {}) as Record<string, unknown>
  return (
    <div className="rounded-xl border-2 border-dashed border-slate-400/50 bg-card/50 px-5 py-4 shadow-lg min-w-[220px] min-h-[100px]">
      <Handle type="target" position={Position.Left} className="!bg-slate-400" />
      <div className="flex items-center gap-2 mb-2">
        <span className="w-6 h-6 rounded-md bg-slate-400/20 flex items-center justify-center text-slate-500 text-xs font-bold">{ }</span>
        <span className="text-xs font-semibold text-foreground">{String(data.label || "Group")}</span>
      </div>
      <div className="text-[10px] text-muted-foreground space-y-0.5">
        <div>Level: {String(config.c4_level || "Container")}</div>
        <div>Collapsed: {config.collapsed ? "yes" : "no"}</div>
        {config.description ? <div className="italic">{String(config.description)}</div> : null}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-slate-400" />
    </div>
  )
}
