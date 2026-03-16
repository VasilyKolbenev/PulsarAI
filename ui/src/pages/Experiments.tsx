import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "@/api/client"
import { Trash2, GitCompare, FlaskConical } from "lucide-react"
import { Badge } from "@/components/ui/Badge"
import { StatusDot } from "@/components/ui/StatusDot"
import { EmptyState } from "@/components/ui/EmptyState"
import { Breadcrumbs } from "@/components/ui/Breadcrumbs"
import { ExperimentDetail } from "@/components/experiments/ExperimentDetail"

const statusVariant: Record<string, "success" | "warning" | "error" | "default"> = {
  running: "warning",
  completed: "success",
  failed: "error",
  queued: "default",
}

export function Experiments() {
  const [experiments, setExperiments] = useState<Array<Record<string, unknown>>>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [compareData, setCompareData] = useState<Record<string, unknown> | null>(null)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)

  const load = () => {
    api.getExperiments().then(setExperiments).catch(() => {})
  }

  useEffect(load, [])

  // Auto-refresh list and detail every 3s while any experiment is running
  useEffect(() => {
    const hasRunning = experiments.some((e) => e.status === "running")
    const detailRunning = detail && detail.status === "running"
    if (!hasRunning && !detailRunning) return

    const timer = setInterval(() => {
      load()
      if (detail && detail.status === "running") {
        api.getExperiment(String(detail.id)).then(setDetail).catch(() => {})
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [experiments, detail])

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleCompare = async () => {
    if (selected.size < 2) return
    try {
      const res = await api.compareExperiments([...selected])
      setCompareData(res)
    } catch {
      // ignore
    }
  }

  const handleDelete = async (id: string) => {
    await api.deleteExperiment(id)
    setSelected((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
    load()
  }

  const handleDetail = async (id: string) => {
    try {
      const exp = await api.getExperiment(id)
      setDetail(exp)
    } catch {
      // ignore
    }
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Dashboard", href: "/dashboard" }, { label: "Experiments" }]} />
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Experiments</h2>
          <p className="text-muted-foreground text-sm mt-1">{experiments.length} total</p>
        </div>
        <button
          onClick={handleCompare}
          disabled={selected.size < 2}
          className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium disabled:opacity-50"
        >
          <GitCompare size={16} />
          Compare ({selected.size})
        </button>
      </div>

      {experiments.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          title="No experiments yet"
          description="Create your first fine-tuning experiment to get started."
          action={
            <Link
              to="/new"
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 transition-colors"
            >
              New Experiment
            </Link>
          }
        />
      ) : (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-secondary/50">
                <th className="w-10 px-3 py-2"></th>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-left px-4 py-2 font-medium">Model</th>
                <th className="text-left px-4 py-2 font-medium">Strategy</th>
                <th className="text-left px-4 py-2 font-medium">Loss</th>
                <th className="text-left px-4 py-2 font-medium">Accuracy</th>
                <th className="text-left px-4 py-2 font-medium">Trainable</th>
                <th className="text-left px-4 py-2 font-medium">Duration</th>
                <th className="text-left px-4 py-2 font-medium">Created</th>
                <th className="w-10 px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
                <tr key={String(exp.id)} className="border-t border-border hover:bg-secondary/30">
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selected.has(String(exp.id))}
                      onChange={() => toggleSelect(String(exp.id))}
                      className="accent-primary"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => handleDetail(String(exp.id))}
                      className="text-primary hover:underline"
                    >
                      {String(exp.name)}
                    </button>
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={statusVariant[String(exp.status)] || "default"}>
                      {exp.status === "running" && <StatusDot status="warning" pulse className="mr-1" />}
                      {String(exp.status)}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground text-xs">{String(exp.model || "—")}</td>
                  <td className="px-4 py-2">
                    {(() => {
                      const a = exp.artifacts as Record<string, unknown> | undefined
                      const s = a?.strategy as string | undefined
                      return s ? <Badge variant="info">{s.toUpperCase()}</Badge> : "—"
                    })()}
                  </td>
                  <td className="px-4 py-2 font-mono">
                    {exp.final_loss != null ? Number(exp.final_loss).toFixed(4) : "—"}
                  </td>
                  <td className="px-4 py-2 font-mono text-success">
                    {(exp.eval_results as Record<string, unknown>)?.overall_accuracy != null
                      ? `${(Number((exp.eval_results as Record<string, unknown>).overall_accuracy) * 100).toFixed(1)}%`
                      : "—"}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {(() => {
                      const a = exp.artifacts as Record<string, unknown> | undefined
                      return a?.trainable_pct != null ? `${Number(a.trainable_pct).toFixed(2)}%` : "—"
                    })()}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground text-xs">
                    {(() => {
                      const a = exp.artifacts as Record<string, unknown> | undefined
                      const m = a?.training_duration_min as number | undefined
                      return m != null ? `${m.toFixed(0)}m` : "—"
                    })()}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{String(exp.created_at || "").slice(0, 16)}</td>
                  <td className="px-3 py-2">
                    <button onClick={() => handleDelete(String(exp.id))} className="text-destructive hover:text-destructive/80">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail panel */}
      {detail && (
        <ExperimentDetail detail={detail} onClose={() => setDetail(null)} />
      )}

      {/* Compare view */}
      {compareData && (
        <div className="bg-card border border-border rounded-lg p-4 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="font-semibold">Comparison</h3>
            <button onClick={() => setCompareData(null)} className="text-muted-foreground text-sm hover:text-foreground">
              Close
            </button>
          </div>
          <pre className="text-xs text-muted-foreground overflow-auto max-h-60">
            {JSON.stringify(compareData, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}


