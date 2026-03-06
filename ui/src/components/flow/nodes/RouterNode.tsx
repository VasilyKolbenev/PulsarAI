import { Route } from "lucide-react"
import { BaseNode } from "./BaseNode"
import type { NodeProps } from "@xyflow/react"

const RISK_BADGE: Record<string, string> = {
  low: "bg-emerald-500/20 text-emerald-300",
  medium: "bg-amber-500/20 text-amber-300",
  high: "bg-orange-500/20 text-orange-300",
  critical: "bg-red-500/20 text-red-300",
}

export function RouterNode({ data }: NodeProps) {
  const config = (data.config ?? {}) as Record<string, unknown>
  const routes = (config.routes ?? []) as string[]
  const agentRole = String(config.agent_role || "")
  const riskLevel = String(config.risk_level || "")
  const requiresApproval = Boolean(config.requires_approval)

  return (
    <BaseNode
      label={String(data.label || "Router")}
      icon={<Route size={14} />}
      color="#f43f5e"
      inputs={[{ id: "input", label: "input" }]}
      outputs={[
        { id: "route_a", label: "route A" },
        { id: "route_b", label: "route B" },
        { id: "fallback", label: "fallback" },
      ]}
      status={String(data.status || "idle") as "idle" | "running" | "done" | "error"}
    >
      {(agentRole || riskLevel || requiresApproval) && (
        <div className="flex flex-wrap gap-1">
          {agentRole ? (
            <span className="px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[9px] uppercase">
              Role: {agentRole}
            </span>
          ) : null}
          {riskLevel ? (
            <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase ${RISK_BADGE[riskLevel] || "bg-muted text-foreground"}`}>
              Risk: {riskLevel}
            </span>
          ) : null}
          {requiresApproval ? (
            <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[9px] uppercase">
              Approval
            </span>
          ) : null}
        </div>
      )}
      {config.strategy ? <div>Strategy: {String(config.strategy)}</div> : null}
      {routes.length > 0 ? (
        <div>Routes: {routes.slice(0, 3).join(", ")}{routes.length > 3 ? "..." : ""}</div>
      ) : null}
    </BaseNode>
  )
}
