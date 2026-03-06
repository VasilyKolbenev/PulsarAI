import { Network } from "lucide-react"
import { BaseNode } from "./BaseNode"
import type { NodeProps } from "@xyflow/react"

const RISK_BADGE: Record<string, string> = {
  low: "bg-emerald-500/20 text-emerald-300",
  medium: "bg-amber-500/20 text-amber-300",
  high: "bg-orange-500/20 text-orange-300",
  critical: "bg-red-500/20 text-red-300",
}

export function GatewayNode({ data }: NodeProps) {
  const config = (data.config ?? {}) as Record<string, unknown>
  const agentRole = String(config.agent_role || "")
  const riskLevel = String(config.risk_level || "")
  const requiresApproval = Boolean(config.requires_approval)

  return (
    <BaseNode
      label={String(data.label || "Gateway")}
      icon={<Network size={14} />}
      color="#d97706"
      inputs={[
        { id: "agents", label: "agents" },
        { id: "config", label: "config" },
      ]}
      outputs={[
        { id: "api", label: "API" },
        { id: "webhook", label: "webhook" },
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
      {config.protocols ? <div>Protocols: {String(config.protocols)}</div> : null}
      {config.auth_method ? <div>Auth: {String(config.auth_method)}</div> : null}
      {config.rate_limit ? <div>Rate: {String(config.rate_limit)}/min</div> : null}
    </BaseNode>
  )
}
