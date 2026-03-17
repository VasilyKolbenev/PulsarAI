import { NavLink, useNavigate } from "react-router-dom"
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
  LogOut,
  User,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ResourceBar } from "@/components/metrics/ResourceBar"
import { useMetrics } from "@/hooks/useMetrics"
import { useAuth } from "@/lib/auth"

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
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate("/login")
  }

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border flex items-center gap-2.5">
        <img src="/logo.svg" alt="Pulsar AI" className="w-8 h-8" />
        <div>
          <h1 className="text-lg font-bold tracking-tight leading-tight">
            <span className="text-primary">Pulsar</span> AI
          </h1>
          <p className="text-[10px] text-muted-foreground">Fine-tuning Platform</p>
        </div>
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
      {isAuthenticated && user && (
        <div className="border-t border-border px-3 py-2.5 flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
            <User size={14} className="text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium truncate">{user.name || user.email}</p>
            <p className="text-[10px] text-muted-foreground truncate">{user.role}</p>
          </div>
          <button
            onClick={handleLogout}
            className="text-muted-foreground hover:text-foreground transition-colors p-1"
            title="Logout"
          >
            <LogOut size={14} />
          </button>
        </div>
      )}
    </aside>
  )
}
