import { NavLink } from "react-router-dom"
import {
  LayoutDashboard,
  FlaskConical,
  Database,
  ListChecks,
  MessageSquare,
  Settings,
  Activity,
  Server,
  Workflow,
  FileText,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ResourceBar } from "@/components/metrics/ResourceBar"
import { useMetrics } from "@/hooks/useMetrics"

const links = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/new", icon: FlaskConical, label: "New Experiment" },
  { to: "/experiments", icon: ListChecks, label: "Experiments" },
  { to: "/datasets", icon: Database, label: "Datasets" },
  { to: "/workflows", icon: Workflow, label: "Workflows" },
  { to: "/monitoring", icon: Activity, label: "Monitoring" },
  { to: "/compute", icon: Server, label: "Compute" },
  { to: "/prompts", icon: FileText, label: "Prompt Lab" },
  { to: "/agent", icon: MessageSquare, label: "Agent Chat" },
  { to: "/settings", icon: Settings, label: "Settings" },
]

export function Sidebar() {
  const { current, connected } = useMetrics()

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-bold tracking-tight">
          <span className="text-primary">Pulsar</span> AI
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">Fine-tuning Platform</p>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/dashboard"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary"
              )
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-border pt-2 pb-2">
        <ResourceBar metrics={current} connected={connected} />
      </div>
    </aside>
  )
}
