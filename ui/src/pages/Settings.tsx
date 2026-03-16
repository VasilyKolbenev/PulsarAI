import { useEffect, useState } from "react"
import { api, setApiKey } from "@/api/client"
import {
  Cpu,
  CheckCircle,
  XCircle,
  Shield,
  Key,
  Server,
  Copy,
  Trash2,
  Plus,
} from "lucide-react"
import { AnimatedPage, FadeIn } from "@/components/ui/AnimatedPage"

interface ServerSettings {
  version: string
  auth_enabled: boolean
  stand_mode: string
  env_profile: string
  cors_origins: string[]
  data_dir: string
}

export function Settings() {
  const [hardware, setHardware] = useState<Record<string, unknown> | null>(null)
  const [health, setHealth] = useState<boolean | null>(null)
  const [settings, setSettings] = useState<ServerSettings | null>(null)
  const [apiKeys, setApiKeys] = useState<Array<{ name: string }>>([])
  const [newKeyName, setNewKeyName] = useState("")
  const [generatedKey, setGeneratedKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    api.getHardware().then(setHardware).catch(() => setHardware(null))
    api.health().then(() => setHealth(true)).catch(() => setHealth(false))
    api.getSettings().then(setSettings).catch(() => {})
    api.listApiKeys().then(setApiKeys).catch(() => {})
  }, [])

  const handleGenerateKey = async () => {
    const name = newKeyName.trim() || "default"
    const result = await api.generateApiKey(name)
    setGeneratedKey(result.key)
    setApiKey(result.key)
    setNewKeyName("")
    api.listApiKeys().then(setApiKeys).catch(() => {})
  }

  const handleRevokeKey = async (name: string) => {
    await api.revokeApiKey(name)
    api.listApiKeys().then(setApiKeys).catch(() => {})
  }

  const handleCopyKey = () => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <AnimatedPage>
      <div className="max-w-2xl space-y-6">
        <div>
          <h2 className="text-2xl font-bold">Settings</h2>
          <p className="text-muted-foreground text-sm mt-1">
            Server configuration, security, and hardware info
          </p>
        </div>

        <FadeIn delay={0}>
          <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-3">
            {health === true ? (
              <CheckCircle className="text-success" size={20} />
            ) : health === false ? (
              <XCircle className="text-destructive" size={20} />
            ) : (
              <div className="w-5 h-5 rounded-full bg-muted animate-pulse" />
            )}
            <div>
              <div className="text-sm font-medium">
                API Server{" "}
                {health === true
                  ? "Online"
                  : health === false
                    ? "Offline"
                    : "Checking..."}
              </div>
              <div className="text-xs text-muted-foreground">
                {health === false && "Start with: pulsar ui"}
              </div>
            </div>
          </div>
        </FadeIn>

        <FadeIn delay={0.05}>
          <div className="bg-card border border-border rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Server size={18} className="text-primary" />
              <h3 className="font-semibold">Server Info</h3>
            </div>
            {settings ? (
              <div className="grid grid-cols-2 gap-3 text-sm">
                <InfoRow label="Version" value={settings.version} />
                <InfoRow
                  label="Auth"
                  value={settings.auth_enabled ? "Enabled" : "Disabled"}
                />
                <InfoRow label="Stand Mode" value={settings.stand_mode} />
                <InfoRow label="Env Profile" value={settings.env_profile} />
                <div className="col-span-2">
                  <div className="text-xs text-muted-foreground">
                    CORS Origins
                  </div>
                  <div className="font-mono text-xs mt-0.5">
                    {settings.cors_origins.join(", ")}
                  </div>
                </div>
                <div className="col-span-2">
                  <div className="text-xs text-muted-foreground">
                    Data Directory
                  </div>
                  <div className="font-mono text-xs mt-0.5 break-all">
                    {settings.data_dir}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Loading...</p>
            )}
          </div>
        </FadeIn>

        <FadeIn delay={0.1}>
          <div className="bg-card border border-border rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Shield size={18} className="text-primary" />
              <h3 className="font-semibold">API Keys</h3>
              {settings && !settings.auth_enabled && (
                <span className="text-[10px] bg-muted text-muted-foreground px-2 py-0.5 rounded ml-auto">
                  Auth disabled - keys stored but not enforced
                </span>
              )}
            </div>

            {generatedKey && (
              <div className="bg-success/10 border border-success/30 rounded-lg p-3 space-y-2">
                <div className="text-xs font-medium text-success">
                  New key generated - copy it now, it will not be shown again
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs font-mono bg-secondary p-2 rounded break-all">
                    {generatedKey}
                  </code>
                  <button
                    onClick={handleCopyKey}
                    className="p-2 hover:bg-secondary rounded transition-colors"
                    title="Copy"
                  >
                    <Copy size={14} />
                  </button>
                </div>
                {copied && (
                  <span className="text-[10px] text-success">Copied!</span>
                )}
              </div>
            )}

            {apiKeys.length > 0 ? (
              <div className="space-y-1">
                {apiKeys.map((k, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-secondary/30"
                  >
                    <div className="flex items-center gap-2">
                      <Key size={12} className="text-muted-foreground" />
                      <span className="text-sm">{k.name}</span>
                    </div>
                    <button
                      onClick={() => handleRevokeKey(k.name)}
                      className="p-1 text-muted-foreground hover:text-destructive transition-colors"
                      title="Revoke"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No API keys generated
              </p>
            )}

            <div className="flex items-center gap-2 pt-2 border-t border-border">
              <input
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="Key name (optional)"
                className="flex-1 px-3 py-1.5 bg-secondary border border-border rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                onClick={handleGenerateKey}
                className="flex items-center gap-1 px-3 py-1.5 bg-primary text-primary-foreground rounded text-xs hover:bg-primary/90 transition-colors"
              >
                <Plus size={12} />
                Generate
              </button>
            </div>
          </div>
        </FadeIn>

        <FadeIn delay={0.15}>
          <div className="bg-card border border-border rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Cpu size={18} className="text-primary" />
              <h3 className="font-semibold">Hardware</h3>
            </div>
            {hardware ? (
              <div className="grid grid-cols-2 gap-3 text-sm">
                <InfoRow
                  label="GPU"
                  value={String(hardware.gpu_name || "N/A")}
                />
                <InfoRow label="GPUs" value={String(hardware.num_gpus || 0)} />
                <InfoRow
                  label="VRAM per GPU"
                  value={`${hardware.vram_per_gpu_gb} GB`}
                />
                <InfoRow
                  label="Total VRAM"
                  value={`${hardware.total_vram_gb} GB`}
                />
                <InfoRow
                  label="BF16 Supported"
                  value={hardware.bf16_supported ? "Yes" : "No"}
                />
                <InfoRow
                  label="Recommended Strategy"
                  value={String(hardware.strategy || "-")}
                />
                <InfoRow
                  label="Batch Size"
                  value={String(hardware.recommended_batch_size || "-")}
                />
                <InfoRow
                  label="Grad Accum"
                  value={String(
                    hardware.recommended_gradient_accumulation || "-"
                  )}
                />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Loading hardware info...
              </p>
            )}
          </div>
        </FadeIn>
      </div>
    </AnimatedPage>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-mono">{value}</div>
    </div>
  )
}
