import { useState } from "react"
import {
  Target, Percent, BarChart3,
  Cpu, Settings, Layers, HardDrive, Timer, ChevronDown, ChevronUp,
} from "lucide-react"
import { LossChart } from "@/components/training/LossChart"
import type { SSEMetrics } from "@/hooks/useSSE"
import { Badge } from "@/components/ui/Badge"

const statusVariant: Record<string, "success" | "warning" | "error" | "default"> = {
  running: "warning",
  completed: "success",
  failed: "error",
  queued: "default",
}

export function ExperimentDetail({ detail, onClose }: { detail: Record<string, unknown>; onClose: () => void }) {
  const artifacts = detail.artifacts as Record<string, unknown> | undefined
  const hp = artifacts?.hyperparameters as Record<string, unknown> | undefined
  const lora = artifacts?.lora as Record<string, unknown> | undefined
  const quant = artifacts?.quantization as Record<string, unknown> | undefined
  const hw = artifacts?.hardware as Record<string, unknown> | undefined
  const ds = artifacts?.dataset as Record<string, unknown> | undefined

  const formatParams = (n: number | undefined) => {
    if (n == null) return "—"
    if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
    if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`
    return String(n)
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-lg">{String(detail.name)}</h3>
        <button onClick={onClose} className="text-muted-foreground text-sm hover:text-foreground">
          Close
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <SummaryCard label="Status" value={String(detail.status)} badge />
        <SummaryCard label="Task" value={String(detail.task || "sft").toUpperCase()} />
        <SummaryCard label="Final Loss" value={detail.final_loss != null ? Number(detail.final_loss).toFixed(4) : "—"} mono />
        <SummaryCard
          label="Accuracy"
          value={
            (detail.eval_results as Record<string, unknown>)?.overall_accuracy != null
              ? `${(Number((detail.eval_results as Record<string, unknown>).overall_accuracy) * 100).toFixed(1)}%`
              : "—"
          }
          highlight
        />
        <SummaryCard
          label="Trainable"
          value={artifacts?.trainable_pct != null ? `${Number(artifacts.trainable_pct).toFixed(2)}%` : "—"}
          sub={`${formatParams(artifacts?.trainable_params as number)} / ${formatParams(artifacts?.total_params as number)}`}
        />
        <SummaryCard
          label="Duration"
          value={artifacts?.training_duration_min != null ? `${Number(artifacts.training_duration_min).toFixed(0)} min` : "—"}
        />
      </div>

      {/* Artifact sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {hp && (
          <CollapsibleSection title="Hyperparameters" icon={<Settings size={14} />}>
            <div className="space-y-0.5">
              <KV label="Epochs" value={hp.epochs as number} mono />
              <KV label="Learning Rate" value={String(hp.learning_rate)} mono />
              <KV label="Batch Size" value={hp.batch_size as number} mono />
              <KV label="Gradient Accumulation" value={hp.gradient_accumulation as number} mono />
              <KV label="Effective Batch" value={((hp.batch_size as number) || 1) * ((hp.gradient_accumulation as number) || 1)} mono />
              <KV label="Optimizer" value={String(hp.optimizer)} />
              <KV label="Max Seq Length" value={hp.max_seq_length as number} mono />
              <KV label="Warmup Steps" value={hp.warmup_steps as number} mono />
              <KV label="Seed" value={hp.seed as number} mono />
            </div>
          </CollapsibleSection>
        )}

        {lora && (
          <CollapsibleSection title="LoRA Configuration" icon={<Layers size={14} />}>
            <div className="space-y-0.5">
              <KV label="Rank (r)" value={lora.r as number} mono />
              <KV label="Alpha" value={lora.alpha as number} mono />
              <KV label="Dropout" value={lora.dropout as number} mono />
              <KV label="PEFT Type" value={lora.peft_type as string} />
              <KV label="Adapter Size" value={artifacts?.adapter_size_mb != null ? `${Number(artifacts.adapter_size_mb).toFixed(1)} MB` : undefined} mono />
              {Array.isArray(lora.target_modules) && (
                <div className="pt-1">
                  <span className="text-muted-foreground text-xs">Target Modules</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(lora.target_modules as string[]).map((m) => (
                      <span key={m} className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-primary/10 text-primary font-mono">{m}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CollapsibleSection>
        )}

        {(artifacts?.strategy || quant) && (
          <CollapsibleSection title="Strategy & Quantization" icon={<Cpu size={14} />}>
            <div className="space-y-0.5">
              <KV label="Strategy" value={artifacts?.strategy as string} />
              {quant && (
                <>
                  <KV label="4-bit Loading" value={quant.load_in_4bit ? "Yes" : "No"} />
                  <KV label="Quant Type" value={quant.bnb_4bit_quant_type as string} />
                  <KV label="Compute Dtype" value={quant.bnb_4bit_compute_dtype as string} />
                </>
              )}
            </div>
          </CollapsibleSection>
        )}

        <CollapsibleSection title="Hardware & Dataset" icon={<HardDrive size={14} />}>
          <div className="space-y-0.5">
            {hw && (
              <>
                <KV label="GPU" value={hw.gpu_name as string} />
                <KV label="VRAM" value={hw.vram_gb != null ? `${hw.vram_gb} GB` : undefined} mono />
                <KV label="BF16" value={hw.bf16 ? "Supported" : "No"} />
              </>
            )}
            <KV label="Model" value={detail.model as string} />
            {ds && (
              <>
                <div className="border-t border-border my-1" />
                <KV label="Dataset" value={ds.path as string} />
                <KV label="Format" value={ds.format as string} />
                <KV label="Test Split" value={ds.test_size != null ? `${(Number(ds.test_size) * 100).toFixed(0)}%` : undefined} />
              </>
            )}
          </div>
        </CollapsibleSection>
      </div>

      {/* Loss chart */}
      {Array.isArray(detail.training_history) && detail.training_history.length > 0 && (
        <CollapsibleSection title="Training Loss" icon={<Timer size={14} />}>
          <LossChart
            data={(detail.training_history as Array<Record<string, unknown>>).map((h) => ({
              step: Number(h.step || 0),
              epoch: Number(h.epoch || 0),
              loss: h.loss != null ? Number(h.loss) : null,
              learning_rate: null,
              gpu_mem_gb: null,
            })) as SSEMetrics[]}
          />
        </CollapsibleSection>
      )}

      {/* Eval Results */}
      <EvalResults data={detail.eval_results as Record<string, unknown> | null} />
    </div>
  )
}

function CollapsibleSection({ title, icon, children, defaultOpen = true }: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 bg-secondary/30 hover:bg-secondary/50 transition-colors text-sm font-medium"
      >
        <span className="flex items-center gap-2">{icon}{title}</span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && <div className="p-3">{children}</div>}
    </div>
  )
}

function KV({ label, value, mono }: { label: string; value: string | number | null | undefined; mono?: boolean }) {
  if (value == null || value === "") return null
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className={`text-xs ${mono ? "font-mono" : ""}`}>{String(value)}</span>
    </div>
  )
}

function SummaryCard({ label, value, mono, badge, highlight, sub }: {
  label: string; value: string; mono?: boolean; badge?: boolean; highlight?: boolean; sub?: string
}) {
  return (
    <div className="bg-secondary/30 rounded-lg p-3 text-center">
      {badge ? (
        <div className="mb-1"><Badge variant={statusVariant[value] || "default"}>{value}</Badge></div>
      ) : (
        <div className={`text-lg font-bold ${highlight ? "text-success" : ""} ${mono ? "font-mono" : ""}`}>
          {value}
        </div>
      )}
      <div className="text-xs text-muted-foreground">{label}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  )
}

function EvalResults({ data }: { data: Record<string, unknown> | null }) {
  if (!data) return null

  const accuracy = data.overall_accuracy as number | undefined
  const parseRate = data.json_parse_rate as number | undefined
  const f1 = data.f1_weighted as Record<string, number> | undefined
  const perColumn = data.per_column as Record<string, Record<string, unknown>> | undefined
  const confusion = data.confusion_matrix as { labels: string[]; matrix: number[][] } | undefined

  return (
    <div className="space-y-3">
      <h4 className="font-semibold flex items-center gap-2">
        <Target size={16} />
        Evaluation Results
      </h4>

      <div className="grid grid-cols-4 gap-3">
        <div className="bg-secondary/50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-success">
            {accuracy != null ? `${(accuracy * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="text-xs text-muted-foreground">Accuracy</div>
        </div>
        <div className="bg-secondary/50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-primary">
            {f1?.f1 != null ? `${(f1.f1 * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="text-xs text-muted-foreground">F1 (weighted)</div>
        </div>
        <div className="bg-secondary/50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-primary">
            {f1?.precision != null ? `${(f1.precision * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="text-xs text-muted-foreground">Precision</div>
        </div>
        <div className="bg-secondary/50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold">
            {parseRate != null ? `${(parseRate * 100).toFixed(0)}%` : "—"}
          </div>
          <div className="text-xs text-muted-foreground">JSON Parse Rate</div>
        </div>
      </div>

      {perColumn && Object.keys(perColumn).length > 0 && (
        <div>
          <h5 className="text-sm font-medium mb-2 flex items-center gap-1">
            <BarChart3 size={14} /> Per-class Accuracy
          </h5>
          {Object.entries(perColumn).map(([col, colData]) => {
            const perClass = colData.per_class as Record<string, { accuracy: number; correct: number; count: number }> | undefined
            if (!perClass) return null
            return (
              <div key={col} className="mb-2">
                <div className="text-xs text-muted-foreground mb-1 uppercase">{col}</div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  {Object.entries(perClass)
                    .sort(([, a], [, b]) => b.count - a.count)
                    .map(([cls, info]) => (
                      <div key={cls} className="flex items-center justify-between bg-secondary/30 rounded px-2 py-1">
                        <span className="truncate mr-1">{cls}</span>
                        <span className={`font-mono ${info.accuracy >= 0.8 ? "text-success" : info.accuracy >= 0.5 ? "text-warning" : "text-destructive"}`}>
                          {(info.accuracy * 100).toFixed(0)}%
                          <span className="text-muted-foreground ml-1">({info.correct}/{info.count})</span>
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {confusion && confusion.labels.length > 0 && confusion.labels.length <= 15 && (
        <div>
          <h5 className="text-sm font-medium mb-2 flex items-center gap-1">
            <Percent size={14} /> Confusion Matrix
          </h5>
          <div className="overflow-x-auto">
            <table className="text-xs border-collapse">
              <thead>
                <tr>
                  <th className="px-1 py-0.5"></th>
                  {confusion.labels.map((l) => (
                    <th key={l} className="px-1 py-0.5 text-muted-foreground font-normal rotate-45 origin-bottom-left whitespace-nowrap" style={{writingMode: "vertical-lr"}}>
                      {l}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {confusion.matrix.map((row, i) => (
                  <tr key={i}>
                    <td className="px-1 py-0.5 text-muted-foreground whitespace-nowrap text-right pr-2">{confusion.labels[i]}</td>
                    {row.map((val, j) => {
                      const maxInRow = Math.max(...row)
                      const isDiag = i === j
                      const opacity = maxInRow > 0 ? Math.max(0.1, val / maxInRow) : 0
                      return (
                        <td
                          key={j}
                          className={`px-1 py-0.5 text-center font-mono ${isDiag ? "font-bold" : ""}`}
                          style={{
                            backgroundColor: isDiag
                              ? `rgba(34, 197, 94, ${opacity * 0.5})`
                              : val > 0
                              ? `rgba(239, 68, 68, ${opacity * 0.4})`
                              : "transparent",
                          }}
                        >
                          {val > 0 ? val : ""}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
