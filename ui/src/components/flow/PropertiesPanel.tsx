import { useState } from "react"
import { ChevronDown, ChevronRight, X } from "lucide-react"
import type { Node } from "@xyflow/react"

interface PropertiesPanelProps {
  node: Node | null
  onClose: () => void
  onUpdate: (nodeId: string, data: Record<string, unknown>) => void
}

interface FieldDef {
  key: string
  label: string
  type: "text" | "number" | "select" | "textarea" | "boolean"
  options?: string[]
  placeholder?: string
}

interface FieldGroup {
  group: string
  fields: FieldDef[]
  collapsed?: boolean
}

const TRAINING_GROUPS: FieldGroup[] = [
  {
    group: "Training",
    fields: [
      { key: "task", label: "Task", type: "select", options: ["sft", "dpo"] },
      { key: "lr", label: "Learning Rate", type: "number", placeholder: "2e-5" },
      { key: "epochs", label: "Epochs", type: "number", placeholder: "3" },
      { key: "batch_size", label: "Batch Size", type: "number", placeholder: "4" },
      { key: "max_seq_length", label: "Max Seq Length", type: "number", placeholder: "2048" },
    ],
  },
  {
    group: "LoRA Config",
    fields: [
      { key: "lora_r", label: "LoRA Rank (r)", type: "number", placeholder: "16" },
      { key: "lora_alpha", label: "LoRA Alpha", type: "number", placeholder: "32" },
      { key: "lora_dropout", label: "LoRA Dropout", type: "number", placeholder: "0.0" },
    ],
    collapsed: true,
  },
  {
    group: "Optimization",
    fields: [
      { key: "optimizer", label: "Optimizer", type: "select", options: ["adamw_8bit", "adamw", "adafactor", "sgd"] },
      { key: "gradient_accumulation_steps", label: "Grad Accum Steps", type: "number", placeholder: "16" },
      { key: "warmup_steps", label: "Warmup Steps", type: "number", placeholder: "10" },
      { key: "weight_decay", label: "Weight Decay", type: "number", placeholder: "0.0" },
      { key: "max_grad_norm", label: "Max Grad Norm", type: "number", placeholder: "1.0" },
    ],
    collapsed: true,
  },
  {
    group: "Advanced",
    fields: [
      { key: "gradient_checkpointing", label: "Gradient Checkpointing", type: "boolean" },
      { key: "bf16", label: "BF16 Training", type: "boolean" },
      { key: "use_unsloth", label: "Use Unsloth", type: "boolean" },
      { key: "seed", label: "Seed", type: "number", placeholder: "42" },
      { key: "logging_steps", label: "Logging Steps", type: "number", placeholder: "20" },
      { key: "save_steps", label: "Save Steps", type: "number", placeholder: "200" },
    ],
    collapsed: true,
  },
]

const DPO_GROUP: FieldGroup = {
  group: "DPO Settings",
  fields: [
    { key: "dpo_beta", label: "DPO Beta", type: "number", placeholder: "0.1" },
    { key: "dpo_max_length", label: "Max Length", type: "number", placeholder: "512" },
    { key: "dpo_max_prompt_length", label: "Max Prompt Length", type: "number", placeholder: "384" },
  ],
  collapsed: true,
}

const AGENT_GOV_FIELDS: FieldDef[] = [
  { key: "agent_role", label: "Agent Role", type: "select", options: ["intake", "kyc_aml", "risk_scoring", "decision", "compliance", "collections", "support"] },
  { key: "risk_level", label: "Risk Level", type: "select", options: ["low", "medium", "high", "critical"] },
  { key: "requires_approval", label: "Requires Approval", type: "boolean" },
]
const FLAT_FIELDS: Record<string, FieldDef[]> = {
  dataSource: [
    { key: "path", label: "File Path", type: "text", placeholder: "/data/train.jsonl" },
    { key: "format", label: "Format", type: "select", options: ["jsonl", "csv", "parquet", "huggingface"] },
    { key: "split", label: "Split", type: "select", options: ["train", "validation", "test"] },
  ],
  model: [
    { key: "model_id", label: "Model ID", type: "text", placeholder: "meta-llama/Llama-3-8B" },
    { key: "quantization", label: "Quantization", type: "select", options: ["none", "4bit", "8bit"] },
  ],
  eval: [
    { key: "batch_size", label: "Batch Size", type: "number", placeholder: "8" },
    { key: "max_tokens", label: "Max Tokens", type: "number", placeholder: "512" },
  ],
  export: [
    { key: "format", label: "Format", type: "select", options: ["gguf", "merged", "lora", "huggingface"] },
    { key: "quantization", label: "Quantization", type: "select", options: ["none", "q4_k_m", "q5_k_m", "q8_0", "f16"] },
  ],
  agent: [
    { key: "framework", label: "Framework", type: "select", options: ["pulsar-react", "langgraph", "crewai", "autogen", "custom"] },
    { key: "system_prompt", label: "System Prompt", type: "textarea", placeholder: "You are a helpful assistant..." },
    { key: "tools", label: "Tools (comma-separated)", type: "text", placeholder: "search,calculator,code" },
    { key: "max_iterations", label: "Max Iterations", type: "number", placeholder: "10" },
    { key: "memory_type", label: "Memory", type: "select", options: ["none", "short_term", "long_term", "both"] },
    ...AGENT_GOV_FIELDS,
  ],
  prompt: [
    { key: "template", label: "Template", type: "textarea", placeholder: "{{input}}\n\nRespond as..." },
    { key: "variables", label: "Variables (comma-separated)", type: "text", placeholder: "input,context" },
  ],
  conditional: [
    { key: "metric_name", label: "Metric", type: "text", placeholder: "accuracy" },
    { key: "operator", label: "Operator", type: "select", options: [">=", ">", "<=", "<", "==", "!="] },
    { key: "threshold", label: "Threshold", type: "number", placeholder: "0.8" },
  ],
  rag: [
    { key: "embedding_model", label: "Embedding Model", type: "text", placeholder: "BAAI/bge-small-en-v1.5" },
    { key: "vector_store", label: "Vector Store", type: "select", options: ["chroma", "faiss", "qdrant", "pinecone"] },
    { key: "chunk_size", label: "Chunk Size", type: "number", placeholder: "512" },
    { key: "chunk_overlap", label: "Chunk Overlap", type: "number", placeholder: "50" },
    { key: "top_k", label: "Top-K Results", type: "number", placeholder: "5" },
    { key: "search_type", label: "Search Type", type: "select", options: ["similarity", "mmr", "hybrid"] },
  ],
  inference: [
    { key: "max_tokens", label: "Max Tokens", type: "number", placeholder: "512" },
    { key: "temperature", label: "Temperature", type: "number", placeholder: "0.7" },
    { key: "top_p", label: "Top-P", type: "number", placeholder: "0.9" },
    { key: "batch_size", label: "Batch Size", type: "number", placeholder: "8" },
    { key: "stop_sequences", label: "Stop Sequences", type: "text", placeholder: "\\n,###" },
    { key: "stream", label: "Streaming", type: "boolean" },
  ],
  router: [
    { key: "strategy", label: "Strategy", type: "select", options: ["llm_classifier", "keyword", "semantic", "round_robin"] },
    { key: "routes", label: "Routes (comma-separated)", type: "text", placeholder: "code,research,chat" },
    { key: "classifier_prompt", label: "Classifier Prompt", type: "textarea", placeholder: "Classify the query into..." },
    { key: "fallback_route", label: "Fallback Route", type: "text", placeholder: "fallback" },
    ...AGENT_GOV_FIELDS,
  ],
  dataGen: [
    { key: "output_format", label: "Output Format", type: "select", options: ["sft", "dpo", "rlhf", "raw_traces"] },
    { key: "num_samples", label: "Num Samples", type: "number", placeholder: "1000" },
    { key: "diversity_threshold", label: "Diversity Threshold", type: "number", placeholder: "0.7" },
    { key: "include_reasoning", label: "Include CoT", type: "boolean" },
    { key: "filter_quality", label: "Quality Filter", type: "boolean" },
  ],
  serve: [
    { key: "engine", label: "Engine", type: "select", options: ["vllm", "llama_cpp", "tgi", "ollama"] },
    { key: "port", label: "Port", type: "number", placeholder: "8000" },
    { key: "max_concurrent", label: "Max Concurrent", type: "number", placeholder: "32" },
    { key: "gpu_memory_utilization", label: "GPU Memory %", type: "number", placeholder: "0.9" },
    { key: "api_format", label: "API Format", type: "select", options: ["openai", "custom", "tgi"] },
  ],
  splitter: [
    { key: "train_ratio", label: "Train Ratio", type: "number", placeholder: "0.8" },
    { key: "val_ratio", label: "Val Ratio", type: "number", placeholder: "0.1" },
    { key: "test_ratio", label: "Test Ratio", type: "number", placeholder: "0.1" },
    { key: "strategy", label: "Strategy", type: "select", options: ["random", "stratified", "temporal"] },
    { key: "seed", label: "Seed", type: "number", placeholder: "42" },
  ],
  mcp: [
    { key: "role", label: "Role", type: "select", options: ["server", "client"] },
    { key: "transport", label: "Transport", type: "select", options: ["stdio", "sse", "streamable_http"] },
    { key: "tools_exposed", label: "Tools (comma-separated)", type: "text", placeholder: "search,calculator,code_exec" },
    { key: "endpoint_url", label: "Endpoint URL", type: "text", placeholder: "http://localhost:3001/mcp" },
    { key: "auth_token", label: "Auth Token Env Var", type: "text", placeholder: "MCP_AUTH_TOKEN" },
  ],
  a2a: [
    { key: "protocol", label: "Protocol", type: "select", options: ["a2a", "custom_rpc", "grpc"] },
    { key: "delegation_mode", label: "Delegation Mode", type: "select", options: ["request_response", "streaming", "fire_and_forget"] },
    { key: "task_timeout", label: "Task Timeout (s)", type: "number", placeholder: "300" },
    { key: "retry_count", label: "Retry Count", type: "number", placeholder: "3" },
    { key: "agent_card_url", label: "Agent Card URL", type: "text", placeholder: "https://agent.example/.well-known/agent.json" },
    ...AGENT_GOV_FIELDS,
  ],
  gateway: [
    { key: "protocols", label: "Protocols", type: "text", placeholder: "REST,GraphQL,gRPC" },
    { key: "auth_method", label: "Auth Method", type: "select", options: ["api_key", "oauth2", "jwt", "none"] },
    { key: "rate_limit", label: "Rate Limit (/min)", type: "number", placeholder: "60" },
    { key: "cors_origins", label: "CORS Origins", type: "text", placeholder: "http://localhost:3000" },
    { key: "load_balancer", label: "Load Balancer", type: "select", options: ["round_robin", "least_connections", "weighted"] },
    { key: "ssl_enabled", label: "SSL/TLS", type: "boolean" },
    ...AGENT_GOV_FIELDS,
  ],
  inputGuard: [
    { key: "rules", label: "Rules", type: "text", placeholder: "pii,injection,toxicity" },
    { key: "action", label: "Default Action", type: "select", options: ["block", "warn", "mask", "log"] },
    { key: "pii_types", label: "PII Types", type: "text", placeholder: "email,phone,ssn,credit_card" },
    { key: "custom_blocklist", label: "Blocklist (comma-sep)", type: "text", placeholder: "word1,word2" },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: ["low", "medium", "high"] },
  ],
  outputGuard: [
    { key: "pii_check", label: "PII Leak Detection", type: "boolean" },
    { key: "json_schema", label: "JSON Validation", type: "boolean" },
    { key: "required_keys", label: "Required JSON Keys", type: "text", placeholder: "answer,sources" },
    { key: "max_length", label: "Max Output Length", type: "number", placeholder: "4096" },
    { key: "regex_pattern", label: "Must Match Regex", type: "text", placeholder: "" },
    { key: "action", label: "Action on Fail", type: "select", options: ["block", "warn", "mask"] },
  ],
  llmJudge: [
    { key: "criteria", label: "Criteria (comma-sep)", type: "text", placeholder: "helpfulness,accuracy,safety" },
    { key: "judge_model", label: "Judge Model", type: "text", placeholder: "claude-sonnet-4-6" },
    { key: "scale_min", label: "Scale Min", type: "number", placeholder: "1" },
    { key: "scale_max", label: "Scale Max", type: "number", placeholder: "5" },
    { key: "comparison_mode", label: "Comparison Mode", type: "boolean" },
  ],
  abTest: [
    { key: "metric", label: "Metric", type: "text", placeholder: "latency_ms" },
    { key: "traffic_split", label: "Traffic Split", type: "text", placeholder: "50/50" },
    { key: "min_samples", label: "Min Samples", type: "number", placeholder: "100" },
    { key: "confidence_level", label: "Confidence Level", type: "number", placeholder: "0.95" },
    { key: "lower_is_better", label: "Lower is Better", type: "boolean" },
  ],
  cache: [
    { key: "strategy", label: "Strategy", type: "select", options: ["exact", "semantic"] },
    { key: "ttl", label: "TTL (seconds)", type: "number", placeholder: "3600" },
    { key: "max_entries", label: "Max Entries", type: "number", placeholder: "10000" },
    { key: "model_partitioned", label: "Partition by Model", type: "boolean" },
  ],
  canary: [
    { key: "canary_weight", label: "Canary Weight (%)", type: "number", placeholder: "10" },
    { key: "error_threshold", label: "Error Threshold (%)", type: "number", placeholder: "5" },
    { key: "min_requests", label: "Min Requests", type: "number", placeholder: "100" },
    { key: "auto_rollback", label: "Auto Rollback", type: "boolean" },
    { key: "auto_promote", label: "Auto Promote", type: "boolean" },
    { key: "promote_after", label: "Promote After (requests)", type: "number", placeholder: "1000" },
  ],
  feedback: [
    { key: "feedback_type", label: "Type", type: "select", options: ["thumbs", "rating", "preference", "text"] },
    { key: "export_format", label: "Export Format", type: "select", options: ["dpo", "sft", "rlhf", "jsonl"] },
    { key: "min_rating", label: "Min Rating for Chosen", type: "number", placeholder: "3" },
    { key: "auto_export", label: "Auto Export", type: "boolean" },
  ],
  tracer: [
    { key: "backend", label: "Backend", type: "select", options: ["local", "opentelemetry", "jaeger"] },
    { key: "cost_tracking", label: "Cost Tracking", type: "boolean" },
    { key: "max_traces", label: "Max Traces", type: "number", placeholder: "1000" },
    { key: "sample_rate", label: "Sample Rate", type: "number", placeholder: "1.0" },
  ],
  group: [
    { key: "c4_level", label: "C4 Level", type: "select", options: ["Context", "Container", "Component"] },
    { key: "description", label: "Description", type: "textarea", placeholder: "Group description..." },
    { key: "collapsed", label: "Collapsed", type: "boolean" },
    { key: "color", label: "Color", type: "text", placeholder: "#94a3b8" },
  ],
}

export function PropertiesPanel({ node, onClose, onUpdate }: PropertiesPanelProps) {
  if (!node) return null

  const nodeType = node.type || "default"
  const config = (node.data.config as Record<string, unknown>) || {}
  const isTraining = nodeType === "training"

  function handleChange(key: string, value: string, fieldType: string) {
    const newConfig = { ...config }
    if (fieldType === "number" && value) {
      newConfig[key] = parseFloat(value)
    } else if (fieldType === "boolean") {
      newConfig[key] = value === "true"
    } else {
      newConfig[key] = value
    }
    onUpdate(node!.id, { ...node!.data, config: newConfig })
  }

  function handleLabelChange(value: string) {
    onUpdate(node!.id, { ...node!.data, label: value })
  }

  // Build groups for training node, or wrap flat fields in a single group
  const groups: FieldGroup[] = isTraining
    ? [
        ...TRAINING_GROUPS,
        ...(config.task === "dpo" ? [DPO_GROUP] : []),
      ]
    : FLAT_FIELDS[nodeType]
      ? [{ group: "", fields: FLAT_FIELDS[nodeType] }]
      : []

  return (
    <div className="w-64 shrink-0 border-l border-border bg-card overflow-y-auto">
      <div className="flex items-center justify-between p-3 border-b border-border">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Properties
        </h3>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X size={14} />
        </button>
      </div>
      <div className="p-3 space-y-3">
        {/* Label */}
        <div>
          <label className="text-[10px] font-medium text-muted-foreground uppercase">
            Label
          </label>
          <input
            type="text"
            value={String(node.data.label || "")}
            onChange={(e) => handleLabelChange(e.target.value)}
            className="w-full mt-1 px-2 py-1.5 bg-secondary border border-border rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Grouped fields */}
        {groups.map((group, gi) => (
          <FieldGroupSection
            key={gi}
            group={group}
            config={config}
            onChange={handleChange}
          />
        ))}

        {/* Node info */}
        <div className="pt-2 border-t border-border text-[10px] text-muted-foreground space-y-1">
          <div>ID: {node.id}</div>
          <div>Type: {nodeType}</div>
        </div>
      </div>
    </div>
  )
}

function FieldGroupSection({
  group,
  config,
  onChange,
}: {
  group: FieldGroup
  config: Record<string, unknown>
  onChange: (key: string, value: string, type: string) => void
}) {
  const [collapsed, setCollapsed] = useState(group.collapsed ?? false)

  return (
    <div>
      {group.group && (
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-1 w-full text-[10px] font-semibold text-muted-foreground uppercase tracking-wide py-1 hover:text-foreground transition-colors"
        >
          {collapsed ? <ChevronRight size={10} /> : <ChevronDown size={10} />}
          {group.group}
        </button>
      )}
      {!collapsed && (
        <div className="space-y-2 mt-1">
          {group.fields.map((field) => (
            <FieldInput
              key={field.key}
              field={field}
              value={config[field.key]}
              onChange={onChange}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: FieldDef
  value: unknown
  onChange: (key: string, value: string, type: string) => void
}) {
  const inputClasses =
    "w-full mt-1 px-2 py-1.5 bg-secondary border border-border rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary"

  if (field.type === "boolean") {
    return (
      <div className="flex items-center justify-between">
        <label className="text-[10px] font-medium text-muted-foreground uppercase">
          {field.label}
        </label>
        <button
          onClick={() => onChange(field.key, value ? "false" : "true", "boolean")}
          className={`w-8 h-4 rounded-full transition-colors relative ${
            value ? "bg-primary" : "bg-muted"
          }`}
        >
          <span
            className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
              value ? "left-4" : "left-0.5"
            }`}
          />
        </button>
      </div>
    )
  }

  return (
    <div>
      <label className="text-[10px] font-medium text-muted-foreground uppercase">
        {field.label}
      </label>
      {field.type === "select" ? (
        <select
          value={String(value || "")}
          onChange={(e) => onChange(field.key, e.target.value, field.type)}
          className={inputClasses}
        >
          <option value="">Select...</option>
          {field.options?.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : field.type === "textarea" ? (
        <textarea
          value={String(value || "")}
          onChange={(e) => onChange(field.key, e.target.value, field.type)}
          placeholder={field.placeholder}
          rows={3}
          className={`${inputClasses} resize-none`}
        />
      ) : (
        <input
          type="text"
          value={String(value ?? "")}
          onChange={(e) => onChange(field.key, e.target.value, field.type)}
          placeholder={field.placeholder}
          className={inputClasses}
        />
      )}
    </div>
  )
}

