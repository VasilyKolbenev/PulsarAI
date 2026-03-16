import { useState, useEffect } from "react"
import {
  Server,
  Plus,
  Trash2,
  Wifi,
  WifiOff,
  MonitorDot,
  RefreshCw,
  HardDrive,
  X,
} from "lucide-react"
import { api } from "@/api/client"
import { EmptyState } from "@/components/ui/EmptyState"
import { Breadcrumbs } from "@/components/ui/Breadcrumbs"

interface ComputeTarget {
  id: string
  name: string
  host: string
  user: string
  port: number
  key_path: string | null
  gpu_count: number
  gpu_type: string
  vram_gb: number
  status: string
  added_at: string
  last_seen: string | null
}

export function Compute() {
  const [targets, setTargets] = useState<ComputeTarget[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [testing, setTesting] = useState<string | null>(null)
  const [detecting, setDetecting] = useState<string | null>(null)

  // Form state
  const [form, setForm] = useState({
    name: "",
    host: "",
    user: "ubuntu",
    port: "22",
    key_path: "",
  })

  const loadTargets = async () => {
    try {
      const data = await api.computeTargets()
      setTargets(data as unknown as ComputeTarget[])
    } catch {
      // server may not be running
    }
  }

  useEffect(() => {
    loadTargets()
  }, [])

  const addTarget = async () => {
    try {
      await api.addComputeTarget({
        name: form.name,
        host: form.host,
        user: form.user,
        port: parseInt(form.port) || 22,
        key_path: form.key_path || undefined,
      })
      setShowAdd(false)
      setForm({ name: "", host: "", user: "ubuntu", port: "22", key_path: "" })
      loadTargets()
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to add target")
    }
  }

  const removeTarget = async (id: string) => {
    try {
      await api.removeComputeTarget(id)
      loadTargets()
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to remove")
    }
  }

  const testConnection = async (id: string) => {
    setTesting(id)
    try {
      const result = await api.testComputeTarget(id)
      alert(
        result.success
          ? `Connected! Latency: ${result.latency_ms}ms`
          : `Failed: ${result.message}`
      )
      loadTargets()
    } catch (e) {
      alert(e instanceof Error ? e.message : "Connection test failed")
    } finally {
      setTesting(null)
    }
  }

  const detectHardware = async (id: string) => {
    setDetecting(id)
    try {
      const result = await api.detectComputeHardware(id)
      if (result.error) {
        alert(`Detection failed: ${result.error}`)
      } else {
        alert(
          `Found ${result.gpu_count} GPU(s): ${result.gpu_type} (${result.vram_gb} GB VRAM)`
        )
      }
      loadTargets()
    } catch (e) {
      alert(e instanceof Error ? e.message : "Detection failed")
    } finally {
      setDetecting(null)
    }
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Dashboard", href: "/dashboard" }, { label: "Compute" }]} />
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Compute Resources</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage local and remote GPU targets
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm hover:bg-primary/90 transition-colors"
        >
          <Plus size={16} />
          Add Target
        </button>
      </div>

      {/* Local machine card */}
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-success/20 flex items-center justify-center">
            <Server size={20} className="text-success" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">Local Machine</span>
              <span className="w-2 h-2 rounded-full bg-success" />
            </div>
            <p className="text-xs text-muted-foreground">
              This computer &mdash; always available
            </p>
          </div>
          <a
            href="/monitoring"
            className="text-xs text-primary hover:underline"
          >
            View metrics →
          </a>
        </div>
      </div>

      {/* Remote targets */}
      {targets.length === 0 ? (
        <EmptyState
          icon={Server}
          title="No remote targets configured"
          description="Add a remote GPU machine to distribute training across multiple nodes."
          action={
            <button
              onClick={() => setShowAdd(true)}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 transition-colors"
            >
              Add Target
            </button>
          }
        />
      ) : (
        <div className="grid gap-4">
          {targets.map((t) => (
            <div
              key={t.id}
              className="bg-card border border-border rounded-lg p-4"
            >
              <div className="flex items-start gap-3">
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    t.status === "online"
                      ? "bg-success/20"
                      : t.status === "offline"
                      ? "bg-destructive/20"
                      : "bg-muted"
                  }`}
                >
                  {t.status === "online" ? (
                    <Wifi size={20} className="text-success" />
                  ) : t.status === "offline" ? (
                    <WifiOff size={20} className="text-destructive" />
                  ) : (
                    <Server size={20} className="text-muted-foreground" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{t.name}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        t.status === "online"
                          ? "bg-success/20 text-success"
                          : t.status === "offline"
                          ? "bg-destructive/20 text-destructive"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {t.status}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {t.user}@{t.host}:{t.port}
                  </p>
                  {t.gpu_count > 0 && (
                    <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <MonitorDot size={12} />
                        {t.gpu_count}× {t.gpu_type}
                      </span>
                      <span className="flex items-center gap-1">
                        <HardDrive size={12} />
                        {t.vram_gb} GB VRAM
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => testConnection(t.id)}
                    disabled={testing === t.id}
                    className="p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-md transition-colors disabled:opacity-50"
                    title="Test connection"
                  >
                    <RefreshCw
                      size={14}
                      className={testing === t.id ? "animate-spin" : ""}
                    />
                  </button>
                  <button
                    onClick={() => detectHardware(t.id)}
                    disabled={detecting === t.id}
                    className="p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-md transition-colors disabled:opacity-50"
                    title="Detect hardware"
                  >
                    <MonitorDot
                      size={14}
                      className={detecting === t.id ? "animate-pulse" : ""}
                    />
                  </button>
                  <button
                    onClick={() => removeTarget(t.id)}
                    className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-md transition-colors"
                    title="Remove target"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Target Modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-xl p-6 w-[28rem] shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Add Compute Target</h2>
              <button
                onClick={() => setShowAdd(false)}
                className="text-muted-foreground hover:text-foreground p-1"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">
                  Name
                </label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="my-gpu-box"
                  className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm focus:ring-1 focus:ring-ring focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="text-xs text-muted-foreground block mb-1">
                    Host
                  </label>
                  <input
                    value={form.host}
                    onChange={(e) => setForm({ ...form, host: e.target.value })}
                    placeholder="192.168.1.100"
                    className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm focus:ring-1 focus:ring-ring focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">
                    Port
                  </label>
                  <input
                    value={form.port}
                    onChange={(e) => setForm({ ...form, port: e.target.value })}
                    className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm focus:ring-1 focus:ring-ring focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">
                  User
                </label>
                <input
                  value={form.user}
                  onChange={(e) => setForm({ ...form, user: e.target.value })}
                  placeholder="ubuntu"
                  className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm focus:ring-1 focus:ring-ring focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">
                  SSH Key Path (optional)
                </label>
                <input
                  value={form.key_path}
                  onChange={(e) =>
                    setForm({ ...form, key_path: e.target.value })
                  }
                  placeholder="~/.ssh/id_rsa"
                  className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm focus:ring-1 focus:ring-ring focus:outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setShowAdd(false)}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                onClick={addTarget}
                disabled={!form.name || !form.host || !form.user}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                Add Target
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
