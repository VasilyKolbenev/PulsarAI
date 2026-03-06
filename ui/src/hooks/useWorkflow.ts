import { useState, useCallback } from "react"
import {
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
  type OnNodesChange,
  type OnEdgesChange,
} from "@xyflow/react"
import { api } from "@/api/client"

export interface WorkflowMeta {
  id: string
  name: string
  created_at: string
  updated_at: string
  run_count: number
  last_run: string | null
}

type NodeRunStatus = "idle" | "running" | "done" | "error"

interface PipelineStepUpdate {
  type: "step_update"
  step: string
  status: "running" | "completed" | "failed" | "skipped"
}

interface PipelineComplete {
  type: "pipeline_complete"
}

interface PipelineError {
  type: "pipeline_error"
  error: string
}

interface PipelineStart {
  type: "pipeline_start"
}

interface PipelineWsError {
  type: "error"
  error: string
}

type PipelineWsMessage =
  | PipelineStepUpdate
  | PipelineComplete
  | PipelineError
  | PipelineStart
  | PipelineWsError

const GOVERNANCE_NODE_TYPES = new Set(["agent", "a2a", "router", "gateway"])

function toStepName(label: string): string {
  return label.toLowerCase().replaceAll(" ", "_")
}

export function useWorkflow() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [workflowName, setWorkflowName] = useState("Untitled Workflow")
  const [savedWorkflows, setSavedWorkflows] = useState<WorkflowMeta[]>([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [templateLoading, setTemplateLoading] = useState(false)

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, animated: true }, eds))
    },
    [setEdges]
  )

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => setSelectedNode(node),
    []
  )

  const updateNodeData = useCallback(
    (nodeId: string, data: Record<string, unknown>) => {
      setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, data } : n)))
      setSelectedNode((prev) => (prev?.id === nodeId ? { ...prev, data } : prev))
    },
    [setNodes]
  )

  const addNode = useCallback(
    (type: string, label: string, position: { x: number; y: number }) => {
      const id = `${type}_${Date.now()}`
      const newNode: Node = {
        id,
        type,
        position,
        data: { label, config: {}, status: "idle" },
      }
      setRunError(null)
      setNodes((nds) => [...nds, newNode])
    },
    [setNodes]
  )

  const clearCanvas = useCallback(() => {
    setNodes([])
    setEdges([])
    setWorkflowId(null)
    setWorkflowName("Untitled Workflow")
    setSelectedNode(null)
    setRunError(null)
  }, [setNodes, setEdges])

  const loadList = useCallback(async () => {
    const list = await api.listWorkflows()
    setSavedWorkflows(list as unknown as WorkflowMeta[])
    return list
  }, [])

  const loadBankingTemplate = useCallback(async () => {
    setTemplateLoading(true)
    setRunError(null)
    try {
      const wf = (await api.createWorkflowFromTemplate("banking_agentoffice", {
        name: "Banking AgentOffice Template",
      })) as {
        id: string
        name: string
        nodes: Array<Record<string, unknown>>
        edges: Array<Record<string, unknown>>
      }

      setWorkflowId(wf.id)
      setWorkflowName(wf.name)
      setNodes(
        wf.nodes.map((n: Record<string, unknown>) => ({
          id: n.id as string,
          type: n.type as string,
          position: n.position as { x: number; y: number },
          data: n.data as Record<string, unknown>,
        }))
      )
      setEdges(
        wf.edges.map((e: Record<string, unknown>) => ({
          id: e.id as string,
          source: e.source as string,
          target: e.target as string,
          sourceHandle: e.sourceHandle as string | undefined,
          targetHandle: e.targetHandle as string | undefined,
          animated: true,
        }))
      )
      setSelectedNode(null)
      await loadList()
      return wf
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Failed to load banking template"
      setRunError(errorMessage)
      return null
    } finally {
      setTemplateLoading(false)
    }
  }, [setNodes, setEdges, loadList])

  const validateRiskGovernance = useCallback((): string | null => {
    const invalid: string[] = []

    for (const node of nodes) {
      if (!GOVERNANCE_NODE_TYPES.has(String(node.type || ""))) continue
      const data = (node.data || {}) as Record<string, unknown>
      const config = (data.config || {}) as Record<string, unknown>
      const riskLevel = String(config.risk_level || "medium").toLowerCase()
      const requiresApproval = Boolean(config.requires_approval)

      if ((riskLevel === "high" || riskLevel === "critical") && !requiresApproval) {
        const label = String(data.label || node.id)
        invalid.push(`${label} (${riskLevel})`)
      }
    }

    if (invalid.length === 0) return null
    return `Approval required: nodes with high/critical risk must have 'requires_approval=true'. Invalid: ${invalid.join(", ")}`
  }, [nodes])

  const save = useCallback(async () => {
    setSaving(true)
    try {
      const result = await api.saveWorkflow({
        name: workflowName,
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          data: n.data,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle,
          targetHandle: e.targetHandle,
        })),
        workflow_id: workflowId ?? undefined,
      })
      setWorkflowId(result.id as string)
      return result
    } finally {
      setSaving(false)
    }
  }, [workflowName, nodes, edges, workflowId])

  const load = useCallback(
    async (id: string) => {
      const wf = (await api.getWorkflow(id)) as {
        id: string
        name: string
        nodes: Array<Record<string, unknown>>
        edges: Array<Record<string, unknown>>
      }
      setWorkflowId(wf.id)
      setWorkflowName(wf.name)
      setNodes(
        wf.nodes.map((n: Record<string, unknown>) => ({
          id: n.id as string,
          type: n.type as string,
          position: n.position as { x: number; y: number },
          data: n.data as Record<string, unknown>,
        }))
      )
      setEdges(
        wf.edges.map((e: Record<string, unknown>) => ({
          id: e.id as string,
          source: e.source as string,
          target: e.target as string,
          sourceHandle: e.sourceHandle as string | undefined,
          targetHandle: e.targetHandle as string | undefined,
          animated: true,
        }))
      )
      setSelectedNode(null)
      setRunError(null)
    },
    [setNodes, setEdges]
  )

  const run = useCallback(async () => {
    setRunError(null)

    const validationError = validateRiskGovernance()
    if (validationError) {
      setRunError(validationError)
      return { status: "blocked", error: validationError }
    }

    let currentWorkflowId = workflowId
    if (!currentWorkflowId) {
      const saved = await save()
      currentWorkflowId = String((saved as { id?: string }).id || "")
      if (!currentWorkflowId) return null
    }

    setRunning(true)
    try {
      const runResult = (await api.runWorkflow(currentWorkflowId)) as {
        pipeline_config?: Record<string, unknown>
      }
      const pipelineConfig = runResult.pipeline_config
      if (!pipelineConfig) {
        throw new Error("Pipeline config was not returned by server")
      }

      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: {
            ...(n.data as Record<string, unknown>),
            status: "idle" as NodeRunStatus,
          },
        }))
      )

      const nodeByStepName = new Map<string, string>()
      nodes.forEach((n) => {
        const label = String((n.data as Record<string, unknown>).label || n.id)
        nodeByStepName.set(toStepName(label), n.id)
      })

      const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws"
      const wsUrl = `${wsProtocol}://${window.location.host}/api/v1/pipeline/run`

      const runViaWebSocket = async () =>
        new Promise<void>((resolve, reject) => {
          const ws = new WebSocket(wsUrl)
          let settled = false

          const finishResolve = () => {
            if (!settled) {
              settled = true
              resolve()
            }
          }

          const finishReject = (error: Error) => {
            if (!settled) {
              settled = true
              reject(error)
            }
          }

          ws.onopen = () => {
            ws.send(JSON.stringify({ pipeline_config: pipelineConfig }))
          }

          ws.onmessage = (event) => {
            try {
              const message = JSON.parse(event.data) as PipelineWsMessage

              if (message.type === "step_update") {
                const nodeId = nodeByStepName.get(message.step)
                if (!nodeId) return

                const statusMap: Record<PipelineStepUpdate["status"], NodeRunStatus> = {
                  running: "running",
                  completed: "done",
                  failed: "error",
                  skipped: "done",
                }

                const nodeStatus = statusMap[message.status]
                setNodes((nds) =>
                  nds.map((n) =>
                    n.id === nodeId
                      ? {
                          ...n,
                          data: {
                            ...(n.data as Record<string, unknown>),
                            status: nodeStatus,
                          },
                        }
                      : n
                  )
                )
                return
              }

              if (message.type === "pipeline_complete") {
                ws.close()
                finishResolve()
                return
              }

              if (message.type === "pipeline_error" || message.type === "error") {
                ws.close()
                finishReject(new Error(message.error))
              }
            } catch {
              // ignore malformed messages
            }
          }

          ws.onerror = () => {
            finishReject(new Error("Pipeline WebSocket connection failed"))
          }

          ws.onclose = () => {
            finishResolve()
          }
        })

      try {
        await runViaWebSocket()
      } catch (wsError) {
        const wsMessage = wsError instanceof Error ? wsError.message : ""
        if (wsMessage !== "Pipeline WebSocket connection failed" && wsMessage !== "Pipeline WebSocket closed before completion") {
          throw wsError
        }

        const syncResult = (await api.runPipelineSync(pipelineConfig)) as {
          status?: string
          error?: string
          outputs?: Record<string, unknown>
        }

        if (syncResult.status !== "completed") {
          throw new Error(syncResult.error || "Pipeline sync run failed")
        }

        const completed = new Set(Object.keys(syncResult.outputs || {}))
        setNodes((nds) =>
          nds.map((n) => {
            const label = String((n.data as Record<string, unknown>).label || n.id)
            const stepName = toStepName(label)
            if (!completed.has(stepName)) return n
            return {
              ...n,
              data: {
                ...(n.data as Record<string, unknown>),
                status: "done" as NodeRunStatus,
              },
            }
          })
        )
      }

      await loadList()
      return runResult
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Workflow run failed"
      setRunError(errorMessage)
      return { status: "failed", error: errorMessage }
    } finally {
      setRunning(false)
    }
  }, [workflowId, save, setNodes, nodes, loadList, validateRiskGovernance])

  const deleteWorkflow = useCallback(
    async (id: string) => {
      await api.deleteWorkflow(id)
      if (workflowId === id) clearCanvas()
      await loadList()
    },
    [workflowId, clearCanvas, loadList]
  )

  return {
    nodes,
    edges,
    workflowId,
    workflowName,
    savedWorkflows,
    selectedNode,
    saving,
    running,
    runError,
    templateLoading,
    setWorkflowName,
    setSelectedNode,
    onNodesChange: onNodesChange as OnNodesChange,
    onEdgesChange: onEdgesChange as OnEdgesChange,
    onConnect,
    onNodeClick,
    updateNodeData,
    addNode,
    clearCanvas,
    loadBankingTemplate,
    save,
    load,
    loadList,
    run,
    deleteWorkflow,
  }
}

