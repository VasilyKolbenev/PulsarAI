import { ArrowLeftRight } from "lucide-react"
import { BaseNode } from "./BaseNode"
import type { NodeProps } from "@xyflow/react"

const RISK_BADGE: Record<string, string> = {
  low: "bg-emerald-500/20 text-emerald-300",
  medium: "bg-amber-500/20 text-amber-300",
  high: "bg-orange-500/20 text-orange-300",
  critical: "bg-red-500/20 text-red-300",
}

export function A2ANode({ data }: NodeProps) {
  const config = (data.config ?? {}) as Record<string, unknown>
  const agentRole = String(config.agent_role || "")
  const riskLevel = String(config.risk_level || "")
  const requiresApproval = Boolean(config.requires_approval)

  return (
    <BaseNode
      label={String(data.label || "A2A")}
      icon={<ArrowLeftRight size={14} />}
      color="#0891b2"
      inputs={[
        { id: "agent_a", label: "agent A" },
        { id: "agent_b", label: "agent B" },
      ]}
      outputs={[
        { id: "result", label: "result" },
        { id: "transcript", label: "transcript" },
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
      {config.protocol ? <div>Protocol: {String(config.protocol)}</div> : null}
      {config.delegation_mode ? <div>Mode: {String(config.delegation_mode)}</div> : null}
    </BaseNode>
  )
}
