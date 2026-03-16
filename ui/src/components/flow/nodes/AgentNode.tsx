import { MessageSquare } from "lucide-react"
import { BaseNode } from "./BaseNode"
import type { NodeProps } from "@xyflow/react"

const FRAMEWORK_LABELS: Record<string, string> = {
  "pulsar-react": "Pulsar ReAct",
  langgraph: "LangGraph",
  crewai: "CrewAI",
  autogen: "AutoGen",
  custom: "Custom",
}

const RISK_BADGE: Record<string, string> = {
  low: "bg-emerald-500/20 text-emerald-300",
  medium: "bg-amber-500/20 text-amber-300",
  high: "bg-orange-500/20 text-orange-300",
  critical: "bg-red-500/20 text-red-300",
}

export function AgentNode({ data }: NodeProps) {
  const config = (data.config ?? {}) as Record<string, unknown>
  const tools = (config.tools ?? []) as string[]
  const framework = String(config.framework || "pulsar-react")
  const agentRole = String(config.agent_role || "")
  const riskLevel = String(config.risk_level || "")
  const requiresApproval = Boolean(config.requires_approval)

  return (
    <BaseNode
      label={String(data.label || "Agent")}
      icon={<MessageSquare size={14} />}
      color="#8b5cf6"
      inputs={[{ id: "model", label: "model" }]}
      outputs={[{ id: "agent", label: "agent" }]}
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
      <div>{FRAMEWORK_LABELS[framework] || framework}</div>
      {tools.length > 0 ? (
        <div>Tools: {tools.slice(0, 3).join(", ")}{tools.length > 3 ? "..." : ""}</div>
      ) : null}
    </BaseNode>
  )
}
