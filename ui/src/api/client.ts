const BASE = "/api/v1"

let _apiKey: string | null = localStorage.getItem("pulsar_api_key")

export function setApiKey(key: string | null) {
  _apiKey = key
  if (key) localStorage.setItem("pulsar_api_key", key)
  else localStorage.removeItem("pulsar_api_key")
}

export function getApiKey(): string | null {
  return _apiKey
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  }
  if (_apiKey) {
    headers["Authorization"] = `Bearer ${_apiKey}`
  }
  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Training
  startTraining: (data: { name: string; config: Record<string, unknown>; task: string }) =>
    request<{ job_id: string; experiment_id: string; status: string }>(
      "/training/start", { method: "POST", body: JSON.stringify(data) }
    ),
  getJobs: () => request<Array<Record<string, unknown>>>("/training/jobs"),
  cancelJob: (id: string) => request<Record<string, unknown>>(`/training/jobs/${id}`, { method: "DELETE" }),

  // Datasets
  uploadDataset: async (file: File) => {
    const form = new FormData()
    form.append("file", file)
    const headers: Record<string, string> = {}
    if (_apiKey) {
      headers["Authorization"] = `Bearer ${_apiKey}`
    }
    const res = await fetch(`${BASE}/datasets/upload`, { method: "POST", body: form, headers })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || `HTTP ${res.status}`)
    }
    return res.json()
  },
  getDatasets: () => request<Array<Record<string, unknown>>>("/datasets"),
  previewDataset: (id: string, rows = 20) =>
    request<{ columns: string[]; rows: Array<Record<string, unknown>>; total_rows: number }>(
      `/datasets/${id}/preview?rows=${rows}`
    ),
  deleteDataset: (id: string) => request<Record<string, unknown>>(`/datasets/${id}`, { method: "DELETE" }),

  // Experiments
  getExperiments: (status?: string) =>
    request<Array<Record<string, unknown>>>(`/experiments${status ? `?status=${status}` : ""}`),
  getExperiment: (id: string) => request<Record<string, unknown>>(`/experiments/${id}`),
  compareExperiments: (ids: string[]) =>
    request<Record<string, unknown>>("/experiments/compare", {
      method: "POST", body: JSON.stringify({ experiment_ids: ids }),
    }),
  deleteExperiment: (id: string) => request<Record<string, unknown>>(`/experiments/${id}`, { method: "DELETE" }),

  // Eval & Export
  runEval: (data: { experiment_id: string; test_data_path: string; batch_size?: number }) =>
    request<Record<string, unknown>>("/evaluation/run", { method: "POST", body: JSON.stringify(data) }),
  exportModel: (data: { experiment_id: string; format?: string; quantization?: string }) =>
    request<Record<string, unknown>>("/export", { method: "POST", body: JSON.stringify(data) }),

  // Hardware
  getHardware: () => request<Record<string, unknown>>("/hardware"),

  // Metrics
  metricsSnapshot: () => request<Record<string, unknown>>("/metrics/snapshot"),

  // Compute
  computeTargets: () => request<Array<Record<string, unknown>>>("/compute/targets"),
  addComputeTarget: (data: { name: string; host: string; user: string; port?: number; key_path?: string }) =>
    request<Record<string, unknown>>("/compute/targets", { method: "POST", body: JSON.stringify(data) }),
  removeComputeTarget: (id: string) =>
    request<Record<string, unknown>>(`/compute/targets/${id}`, { method: "DELETE" }),
  testComputeTarget: (id: string) =>
    request<{ success: boolean; message: string; latency_ms: number }>(`/compute/targets/${id}/test`, { method: "POST" }),
  detectComputeHardware: (id: string) =>
    request<Record<string, unknown>>(`/compute/targets/${id}/detect`, { method: "POST" }),

  // Workflows
  listWorkflows: () => request<Array<Record<string, unknown>>>("/workflows"),
  saveWorkflow: (data: { name: string; nodes: Record<string, unknown>[]; edges: Record<string, unknown>[]; workflow_id?: string }) =>
    request<Record<string, unknown>>("/workflows", { method: "POST", body: JSON.stringify(data) }),
  getWorkflow: (id: string) => request<Record<string, unknown>>(`/workflows/${id}`),
  deleteWorkflow: (id: string) => request<Record<string, unknown>>(`/workflows/${id}`, { method: "DELETE" }),
  runWorkflow: (id: string) => request<Record<string, unknown>>(`/workflows/${id}/run`, { method: "POST" }),
  runPipelineSync: (pipelineConfig: Record<string, unknown>) =>
    request<Record<string, unknown>>("/pipeline/run/sync", {
      method: "POST",
      body: JSON.stringify({ pipeline_config: pipelineConfig }),
    }),
  getWorkflowConfig: (id: string) => request<Record<string, unknown>>(`/workflows/${id}/config`),
  listWorkflowTemplates: () => request<Array<Record<string, unknown>>>("/workflows/templates"),
  createWorkflowFromTemplate: (templateId: string, data?: { name?: string }) =>
    request<Record<string, unknown>>(`/workflows/templates/${templateId}/create`, { method: "POST", body: JSON.stringify(data || {}) }),

  // Prompts
  listPrompts: (tag?: string) =>
    request<Array<Record<string, unknown>>>(`/prompts${tag ? `?tag=${tag}` : ""}`),
  createPrompt: (data: { name: string; system_prompt: string; description?: string; model?: string; parameters?: Record<string, unknown>; tags?: string[] }) =>
    request<Record<string, unknown>>("/prompts", { method: "POST", body: JSON.stringify(data) }),
  getPrompt: (id: string) => request<Record<string, unknown>>(`/prompts/${id}`),
  updatePrompt: (id: string, data: { name?: string; description?: string; tags?: string[] }) =>
    request<Record<string, unknown>>(`/prompts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePrompt: (id: string) => request<Record<string, unknown>>(`/prompts/${id}`, { method: "DELETE" }),
  addPromptVersion: (id: string, data: { system_prompt: string; model?: string; parameters?: Record<string, unknown> }) =>
    request<Record<string, unknown>>(`/prompts/${id}/versions`, { method: "POST", body: JSON.stringify(data) }),
  getPromptVersion: (id: string, version: number) =>
    request<Record<string, unknown>>(`/prompts/${id}/versions/${version}`),
  diffPromptVersions: (id: string, v1: number, v2: number) =>
    request<Record<string, unknown>>(`/prompts/${id}/diff?v1=${v1}&v2=${v2}`),
  testPrompt: (id: string, data: { variables?: Record<string, string>; version?: number }) =>
    request<Record<string, unknown>>(`/prompts/${id}/test`, { method: "POST", body: JSON.stringify(data) }),

  // Settings
  getSettings: () =>
    request<{
      version: string
      auth_enabled: boolean
      stand_mode: string
      env_profile: string
      cors_origins: string[]
      data_dir: string
    }>("/settings"),
  listApiKeys: () => request<Array<{ name: string }>>("/settings/keys"),
  generateApiKey: (name: string) =>
    request<{ key: string; name: string }>("/settings/keys", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  revokeApiKey: (name: string) =>
    request<{ status: string }>(`/settings/keys/${name}`, { method: "DELETE" }),

  // Health
  health: () => request<{ status: string }>("/health"),

  // Assistant
  assistantChat: (data: { message: string; session_id?: string; context?: Record<string, unknown> }) =>
    request<{
      answer: string
      session_id: string
      actions: Array<Record<string, unknown>>
      mode: string
    }>("/assistant/chat", { method: "POST", body: JSON.stringify(data) }),
  assistantStatus: () =>
    request<{
      active_jobs: Array<Record<string, unknown>>
      recent_experiments: Array<Record<string, unknown>>
      llm_available: boolean
    }>("/assistant/status"),
}

export function sseUrl(jobId: string) {
  return `${BASE}/training/progress/${jobId}`
}

export function metricsLiveUrl() {
  return `${BASE}/metrics/live`
}
