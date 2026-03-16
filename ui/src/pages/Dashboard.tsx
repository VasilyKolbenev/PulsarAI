import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  FlaskConical,
  Database,
  Cpu,
  MonitorDot,
  Workflow,
  FileText,
  Server,
  ArrowRight,
} from "lucide-react"
import {
  AreaChart,
  Area,
  ResponsiveContainer,
} from "recharts"
import { api } from "@/api/client"
import { useMetrics } from "@/hooks/useMetrics"
import { AnimatedPage, FadeIn } from "@/components/ui/AnimatedPage"
import { MetricCard } from "@/components/ui/MetricCard"
import { Badge } from "@/components/ui/Badge"
import { StatusDot } from "@/components/ui/StatusDot"
import { Card, CardHeader, CardTitle } from "@/components/ui/Card"
import { EmptyState } from "@/components/ui/EmptyState"

const statusVariant: Record<string, "success" | "warning" | "error" | "default"> = {
  running: "warning",
  completed: "success",
  failed: "error",
  queued: "default",
  cancelled: "default",
}

export function Dashboard() {
  const [experiments, setExperiments] = useState<Array<Record<string, unknown>>>([])
  const [hardware, setHardware] = useState<Record<string, unknown> | null>(null)
  const [datasets, setDatasets] = useState<Array<Record<string, unknown>>>([])
  const [workflows, setWorkflows] = useState<Array<Record<string, unknown>>>([])
  const [prompts, setPrompts] = useState<Array<Record<string, unknown>>>([])
  const { current, history } = useMetrics()

  useEffect(() => {
    api.getExperiments().then(setExperiments).catch(() => {})
    api.getHardware().then(setHardware).catch(() => {})
    api.getDatasets().then(setDatasets).catch(() => {})
    api.listWorkflows().then(setWorkflows).catch(() => {})
    api.listPrompts().then(setPrompts).catch(() => {})
  }, [])

  const running = experiments.filter((e) => e.status === "running").length
  const completed = experiments.filter((e) => e.status === "completed").length
  const gpu = current?.gpus[0]

  // Mini chart data (last 60 points = 2 min)
  const miniChart = history.slice(-60).map((m, i) => ({
    t: i,
    gpu: m.gpus[0]?.utilization_percent ?? 0,
    cpu: m.cpu_percent,
  }))

  return (
    <AnimatedPage>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold">Dashboard</h2>
          <p className="text-muted-foreground text-sm mt-1">
            Overview of your fine-tuning platform
          </p>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <FadeIn delay={0}>
            <MetricCard
              icon={FlaskConical}
              label="Experiments"
              value={experiments.length}
              subtext={`${running} running · ${completed} completed`}
            />
          </FadeIn>
          <FadeIn delay={0.05}>
            <MetricCard
              icon={Database}
              label="Datasets"
              value={datasets.length}
              subtext="uploaded"
            />
          </FadeIn>
          <FadeIn delay={0.1}>
            <MetricCard
              icon={Workflow}
              label="Workflows"
              value={workflows.length}
              subtext="saved pipelines"
            />
          </FadeIn>
          <FadeIn delay={0.15}>
            <MetricCard
              icon={FileText}
              label="Prompts"
              value={prompts.length}
              subtext="versioned"
            />
          </FadeIn>
        </div>

        {/* GPU + CPU mini charts */}
        <FadeIn delay={0.2}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* GPU card */}
            <Card>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-primary/10">
                  <MonitorDot size={16} className="text-primary" />
                </div>
                <div>
                  <div className="text-sm font-medium">GPU</div>
                  <div className="text-[10px] text-muted-foreground">
                    {gpu ? gpu.name : hardware ? String(hardware.gpu_name || "N/A") : "detecting..."}
                  </div>
                </div>
                <div className="ml-auto text-right">
                  <div className="text-lg font-bold">
                    {gpu ? `${Math.round(gpu.utilization_percent)}%` : "—"}
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    {gpu ? `${gpu.memory_used_gb.toFixed(1)}/${gpu.memory_total_gb.toFixed(1)} GB` : ""}
                  </div>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <AreaChart data={miniChart}>
                  <defs>
                    <linearGradient id="gpuGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6d5dfc" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6d5dfc" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="gpu"
                    stroke="#6d5dfc"
                    fill="url(#gpuGrad)"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            {/* CPU card */}
            <Card>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-success/10">
                  <Cpu size={16} className="text-success" />
                </div>
                <div>
                  <div className="text-sm font-medium">CPU</div>
                  <div className="text-[10px] text-muted-foreground">
                    {current ? `${current.cpu_count} cores` : "detecting..."}
                  </div>
                </div>
                <div className="ml-auto text-right">
                  <div className="text-lg font-bold">
                    {current ? `${Math.round(current.cpu_percent)}%` : "—"}
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    {current ? `${current.ram_used_gb.toFixed(1)}/${current.ram_total_gb.toFixed(1)} GB RAM` : ""}
                  </div>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <AreaChart data={miniChart}>
                  <defs>
                    <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="cpu"
                    stroke="#22c55e"
                    fill="url(#cpuGrad)"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            {/* Quick actions card */}
            <Card className="flex flex-col">
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <div className="space-y-2 flex-1">
                <QuickAction to="/new" icon={FlaskConical} label="New Experiment" color="#6d5dfc" />
                <QuickAction to="/workflows" icon={Workflow} label="Build Workflow" color="#22c55e" />
                <QuickAction to="/prompts" icon={FileText} label="New Prompt" color="#06b6d4" />
                <QuickAction to="/compute" icon={Server} label="Add Compute" color="#f97316" />
              </div>
            </Card>
          </div>
        </FadeIn>

        {/* Recent experiments */}
        <FadeIn delay={0.25}>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Recent Experiments</CardTitle>
              <Link
                to="/experiments"
                className="flex items-center gap-1 text-xs text-primary hover:text-primary/80"
              >
                View all <ArrowRight size={12} />
              </Link>
            </CardHeader>
            {experiments.length === 0 ? (
              <EmptyState
                icon={FlaskConical}
                title="No experiments yet"
                description="Start your first fine-tuning experiment to see results here."
                action={
                  <Link
                    to="/new"
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 transition-colors"
                  >
                    New Experiment
                  </Link>
                }
                className="py-8"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                      <th className="text-left px-3 py-2 font-medium">Name</th>
                      <th className="text-left px-3 py-2 font-medium">Status</th>
                      <th className="text-left px-3 py-2 font-medium">Task</th>
                      <th className="text-right px-3 py-2 font-medium">Loss</th>
                      <th className="text-right px-3 py-2 font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {experiments.slice(0, 8).map((exp) => {
                      const status = String(exp.status)
                      return (
                        <tr
                          key={String(exp.id)}
                          className="border-t border-border/50 hover:bg-secondary/30 transition-colors"
                        >
                          <td className="px-3 py-2">
                            <Link to="/experiments" className="text-primary hover:underline text-xs">
                              {String(exp.name)}
                            </Link>
                          </td>
                          <td className="px-3 py-2">
                            <Badge variant={statusVariant[status] || "default"}>
                              {status === "running" && <StatusDot status="warning" pulse className="mr-1" />}
                              {status}
                            </Badge>
                          </td>
                          <td className="px-3 py-2 text-xs text-muted-foreground">
                            {String(exp.task || "sft").toUpperCase()}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-xs">
                            {exp.final_loss != null ? Number(exp.final_loss).toFixed(4) : "—"}
                          </td>
                          <td className="px-3 py-2 text-right text-xs text-muted-foreground">
                            {String(exp.created_at || "").slice(0, 10)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </FadeIn>
      </div>
    </AnimatedPage>
  )
}

function QuickAction({
  to,
  icon: Icon,
  label,
  color,
}: {
  to: string
  icon: React.ComponentType<{ size?: number }>
  label: string
  color: string
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2.5 px-3 py-2 rounded-md hover:bg-secondary transition-colors group"
    >
      <div
        className="w-6 h-6 rounded flex items-center justify-center shrink-0"
        style={{ backgroundColor: `${color}15`, color }}
      >
        <Icon size={13} />
      </div>
      <span className="text-xs">{label}</span>
      <ArrowRight
        size={12}
        className="ml-auto text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
      />
    </Link>
  )
}
