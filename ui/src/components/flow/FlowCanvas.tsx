import { useCallback, useRef, type DragEvent } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  type ReactFlowInstance,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"

import { DataSourceNode } from "./nodes/DataSourceNode"
import { ModelNode } from "./nodes/ModelNode"
import { TrainingNode } from "./nodes/TrainingNode"
import { EvalNode } from "./nodes/EvalNode"
import { ExportNode } from "./nodes/ExportNode"
import { AgentNode } from "./nodes/AgentNode"
import { PromptNode } from "./nodes/PromptNode"
import { ConditionalNode } from "./nodes/ConditionalNode"
import { RAGNode } from "./nodes/RAGNode"
import { InferenceNode } from "./nodes/InferenceNode"
import { RouterNode } from "./nodes/RouterNode"
import { DataGenNode } from "./nodes/DataGenNode"
import { ServeNode } from "./nodes/ServeNode"
import { SplitterNode } from "./nodes/SplitterNode"
import { MCPNode } from "./nodes/MCPNode"
import { A2ANode } from "./nodes/A2ANode"
import { GatewayNode } from "./nodes/GatewayNode"
import { InputGuardNode } from "./nodes/InputGuardNode"
import { OutputGuardNode } from "./nodes/OutputGuardNode"
import { LLMJudgeNode } from "./nodes/LLMJudgeNode"
import { ABTestNode } from "./nodes/ABTestNode"
import { CacheNode } from "./nodes/CacheNode"
import { CanaryNode } from "./nodes/CanaryNode"
import { FeedbackNode } from "./nodes/FeedbackNode"
import { TracerNode } from "./nodes/TracerNode"
import { GroupNode } from "./nodes/GroupNode"
import type { useWorkflow } from "@/hooks/useWorkflow"

const nodeTypes = {
  dataSource: DataSourceNode,
  model: ModelNode,
  training: TrainingNode,
  eval: EvalNode,
  export: ExportNode,
  agent: AgentNode,
  prompt: PromptNode,
  conditional: ConditionalNode,
  rag: RAGNode,
  inference: InferenceNode,
  router: RouterNode,
  dataGen: DataGenNode,
  serve: ServeNode,
  splitter: SplitterNode,
  mcp: MCPNode,
  a2a: A2ANode,
  gateway: GatewayNode,
  inputGuard: InputGuardNode,
  outputGuard: OutputGuardNode,
  llmJudge: LLMJudgeNode,
  abTest: ABTestNode,
  cache: CacheNode,
  canary: CanaryNode,
  feedback: FeedbackNode,
  tracer: TracerNode,
  group: GroupNode,
}

type WorkflowHook = ReturnType<typeof useWorkflow>

interface FlowCanvasProps {
  workflow: WorkflowHook
}

export function FlowCanvas({ workflow }: FlowCanvasProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const rfInstance = useRef<ReactFlowInstance | null>(null)

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
  }, [])

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault()
      const type = e.dataTransfer.getData("application/reactflow-type")
      const label = e.dataTransfer.getData("application/reactflow-label")
      if (!type || !rfInstance.current || !reactFlowWrapper.current) return

      const bounds = reactFlowWrapper.current.getBoundingClientRect()
      const position = rfInstance.current.screenToFlowPosition({
        x: e.clientX - bounds.left,
        y: e.clientY - bounds.top,
      })

      workflow.addNode(type, label, position)
    },
    [workflow]
  )

  return (
    <div ref={reactFlowWrapper} className="flex-1 h-full">
      <ReactFlow
        nodes={workflow.nodes}
        edges={workflow.edges}
        onNodesChange={workflow.onNodesChange}
        onEdgesChange={workflow.onEdgesChange}
        onConnect={workflow.onConnect}
        onNodeClick={workflow.onNodeClick}
        onPaneClick={() => workflow.setSelectedNode(null)}
        onInit={(instance) => { rfInstance.current = instance }}
        onDragOver={onDragOver}
        onDrop={onDrop}
        nodeTypes={nodeTypes}
        fitView
        deleteKeyCode={["Backspace", "Delete"]}
        className="bg-background"
        defaultEdgeOptions={{ animated: true }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="var(--color-border)"
        />
        <Controls
          className="!bg-card !border-border !shadow-lg [&>button]:!bg-card [&>button]:!border-border [&>button]:!fill-foreground [&>button:hover]:!bg-secondary"
        />
        <MiniMap
          className="!bg-card !border-border"
          maskColor="rgba(0,0,0,0.6)"
          nodeColor={(n) => {
            const colors: Record<string, string> = {
              dataSource: "#22c55e",
              model: "#3b82f6",
              training: "#6d5dfc",
              eval: "#eab308",
              export: "#ef4444",
              agent: "#8b5cf6",
              prompt: "#06b6d4",
              conditional: "#f97316",
              rag: "#0ea5e9",
              inference: "#a855f7",
              router: "#f43f5e",
              dataGen: "#14b8a6",
              serve: "#ec4899",
              splitter: "#84cc16",
              mcp: "#7c3aed",
              a2a: "#0891b2",
              gateway: "#d97706",
              inputGuard: "#ef4444",
              outputGuard: "#f97316",
              llmJudge: "#8b5cf6",
              abTest: "#ec4899",
              cache: "#f59e0b",
              canary: "#10b981",
              feedback: "#0ea5e9",
              tracer: "#6366f1",
              group: "#94a3b8",
            }
            return colors[n.type || ""] || "#6d5dfc"
          }}
        />
      </ReactFlow>
    </div>
  )
}
