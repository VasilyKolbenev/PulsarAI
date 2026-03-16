import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import {
  GraduationCap,
  Workflow,
  Rocket,
  Activity,
  RefreshCw,
  Github,
  ArrowRight,
  Copy,
  Check,
} from "lucide-react"
import { useState } from "react"

/* ------------------------------------------------------------------ */
/*  Animation helpers                                                  */
/* ------------------------------------------------------------------ */

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: "easeOut" as const },
  }),
}

const stagger = {
  visible: { transition: { staggerChildren: 0.1 } },
}

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const pillars = [
  {
    icon: GraduationCap,
    title: "Train",
    desc: "SFT + DPO + LoRA/QLoRA with hardware auto-detection. Fine-tune any model on your data.",
    color: "#6d5dfc",
  },
  {
    icon: Workflow,
    title: "Orchestrate",
    desc: "Visual DAG builder with 26 node types. Build complex training and data pipelines visually.",
    color: "#3b82f6",
  },
  {
    icon: Rocket,
    title: "Deploy",
    desc: "One-click export to GGUF / vLLM / Ollama. From fine-tuned weights to production in minutes.",
    color: "#22c55e",
  },
  {
    icon: Activity,
    title: "Monitor",
    desc: "Real-time GPU/CPU metrics, experiment tracking, and cost analysis. Full observability.",
    color: "#f59e0b",
  },
  {
    icon: RefreshCw,
    title: "Evolve",
    desc: "Agent traces become training data that produce better models. The closed-loop flywheel.",
    color: "#ec4899",
  },
]

const flywheelSteps = [
  { label: "Data", angle: 0 },
  { label: "Train", angle: 60 },
  { label: "Deploy", angle: 120 },
  { label: "Agent", angle: 180 },
  { label: "Collect", angle: 240 },
  { label: "Retrain", angle: 300 },
]

interface ComparisonRow {
  feature: string
  pulsar: boolean
  openjarvis: boolean
  clearml: boolean
  wandb: boolean
  langsmith: boolean
}

const comparisonData: ComparisonRow[] = [
  { feature: "Training (SFT/DPO)", pulsar: true, openjarvis: true, clearml: true, wandb: false, langsmith: false },
  { feature: "Visual Orchestration", pulsar: true, openjarvis: false, clearml: true, wandb: false, langsmith: false },
  { feature: "Agent Framework", pulsar: true, openjarvis: true, clearml: false, wandb: false, langsmith: true },
  { feature: "Self-hosted", pulsar: true, openjarvis: true, clearml: true, wandb: false, langsmith: false },
  { feature: "Closed-loop Pipeline", pulsar: true, openjarvis: false, clearml: false, wandb: false, langsmith: false },
  { feature: "Open Source", pulsar: true, openjarvis: true, clearml: true, wandb: false, langsmith: false },
]

/* ------------------------------------------------------------------ */
/*  Subcomponents                                                      */
/* ------------------------------------------------------------------ */

function Flywheel() {
  const r = 120
  const cx = 160
  const cy = 160

  return (
    <motion.div
      className="relative mx-auto"
      style={{ width: 320, height: 320 }}
      initial={{ opacity: 0, scale: 0.85, rotate: -30 }}
      animate={{ opacity: 1, scale: 1, rotate: 0 }}
      transition={{ duration: 0.8, ease: "easeOut", delay: 0.3 }}
    >
      <svg viewBox="0 0 320 320" className="w-full h-full">
        {/* Outer glow ring */}
        <circle
          cx={cx}
          cy={cy}
          r={r + 20}
          fill="none"
          stroke="url(#glowGradient)"
          strokeWidth="1"
          opacity="0.3"
        />
        {/* Main ring */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="url(#ringGradient)"
          strokeWidth="2"
          strokeDasharray="6 4"
        />
        {/* Animated orbit circle */}
        <circle r="4" fill="#6d5dfc">
          <animateMotion
            dur="8s"
            repeatCount="indefinite"
            path={`M${cx + r},${cy} A${r},${r} 0 1,1 ${cx + r - 0.01},${cy}`}
          />
        </circle>
        {/* Gradient definitions */}
        <defs>
          <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6d5dfc" />
            <stop offset="50%" stopColor="#3b82f6" />
            <stop offset="100%" stopColor="#ec4899" />
          </linearGradient>
          <radialGradient id="glowGradient" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#6d5dfc" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#6d5dfc" stopOpacity="0" />
          </radialGradient>
        </defs>
        {/* Arrow arcs between nodes */}
        {flywheelSteps.map((_, i) => {
          const nextI = (i + 1) % flywheelSteps.length
          const a1 = (flywheelSteps[i].angle - 90) * (Math.PI / 180)
          const a2 = (flywheelSteps[nextI].angle - 90) * (Math.PI / 180)
          const midAngle = (a1 + a2 + (a2 < a1 ? Math.PI * 2 : 0)) / 2
          const x1 = cx + Math.cos(a1) * (r - 8)
          const y1 = cy + Math.sin(a1) * (r - 8)
          const mx = cx + Math.cos(midAngle) * (r - 20)
          const my = cy + Math.sin(midAngle) * (r - 20)
          const x2 = cx + Math.cos(a2) * (r - 8)
          const y2 = cy + Math.sin(a2) * (r - 8)
          return (
            <path
              key={i}
              d={`M${x1},${y1} Q${mx},${my} ${x2},${y2}`}
              fill="none"
              stroke="#6d5dfc"
              strokeWidth="1"
              opacity="0.15"
            />
          )
        })}
        {/* Center text */}
        <text
          x={cx}
          y={cy - 6}
          textAnchor="middle"
          fill="#6d5dfc"
          fontSize="11"
          fontWeight="600"
          letterSpacing="0.1em"
        >
          CLOSED
        </text>
        <text
          x={cx}
          y={cy + 10}
          textAnchor="middle"
          fill="#6d5dfc"
          fontSize="11"
          fontWeight="600"
          letterSpacing="0.1em"
        >
          LOOP
        </text>
      </svg>
      {/* Node labels around the ring */}
      {flywheelSteps.map((step) => {
        const angle = (step.angle - 90) * (Math.PI / 180)
        const nx = cx + Math.cos(angle) * r
        const ny = cy + Math.sin(angle) * r
        return (
          <div
            key={step.label}
            className="absolute flex items-center justify-center w-16 h-16 -ml-8 -mt-8 rounded-full
                       bg-card border border-border text-xs font-semibold text-foreground
                       shadow-lg shadow-primary/5"
            style={{ left: nx, top: ny }}
          >
            {step.label}
          </div>
        )
      })}
    </motion.div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {
      /* clipboard API may be unavailable */
    })
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-3 right-3 p-1.5 rounded-md bg-white/5 hover:bg-white/10
                 text-muted-foreground hover:text-foreground transition-colors"
      aria-label="Copy to clipboard"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Landing Component                                             */
/* ------------------------------------------------------------------ */

export function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden">
      {/* ============================================================ */}
      {/*  HERO                                                        */}
      {/* ============================================================ */}
      <section className="relative min-h-screen flex flex-col items-center justify-center px-6 py-24">
        {/* Background radial glow */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 50% 40%, rgba(109,93,252,0.12) 0%, transparent 70%)",
          }}
        />

        <motion.div
          className="relative z-10 text-center max-w-3xl mx-auto"
          initial="hidden"
          animate="visible"
          variants={stagger}
        >
          <motion.h1
            className="text-6xl md:text-7xl font-extrabold tracking-tight mb-4"
            variants={fadeUp}
            custom={0}
          >
            <span className="text-primary">Pulsar</span>{" "}
            <span className="text-foreground">AI</span>
          </motion.h1>

          <motion.p
            className="text-xl md:text-2xl font-medium text-muted-foreground mb-2"
            variants={fadeUp}
            custom={1}
          >
            The Closed-Loop LLM Platform
          </motion.p>

          <motion.p
            className="text-base text-muted-foreground/70 max-w-xl mx-auto mb-10"
            variants={fadeUp}
            custom={2}
          >
            From raw data to deployed agent. One platform, zero fragmentation.
          </motion.p>

          <motion.div
            className="flex flex-wrap items-center justify-center gap-4 mb-16"
            variants={fadeUp}
            custom={3}
          >
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold text-sm
                         bg-primary text-primary-foreground hover:brightness-110 transition-all
                         shadow-lg shadow-primary/25"
            >
              Get Started <ArrowRight size={16} />
            </Link>
            <a
              href="https://github.com/pulsar-ai/pulsar"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold text-sm
                         border border-border text-muted-foreground hover:text-foreground
                         hover:border-muted-foreground/40 transition-all"
            >
              <Github size={16} /> View on GitHub
            </a>
          </motion.div>
        </motion.div>

        {/* Flywheel visual */}
        <div className="relative z-10 mt-2">
          <Flywheel />
        </div>

        {/* Scroll indicator */}
        <motion.div
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
          animate={{ y: [0, 8, 0] }}
          transition={{ repeat: Infinity, duration: 2 }}
        >
          <div className="w-5 h-8 rounded-full border-2 border-muted-foreground/30 flex items-start justify-center pt-1.5">
            <div className="w-1 h-1.5 rounded-full bg-muted-foreground/50" />
          </div>
        </motion.div>
      </section>

      {/* ============================================================ */}
      {/*  FIVE PILLARS                                                */}
      {/* ============================================================ */}
      <section className="relative px-6 py-24 max-w-6xl mx-auto">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 80% 40% at 50% 0%, rgba(109,93,252,0.06) 0%, transparent 70%)",
          }}
        />

        <motion.div
          className="text-center mb-16 relative z-10"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-3xl md:text-4xl font-bold mb-3">Five Pillars</h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            Everything you need to build, deploy, and evolve LLM-powered products.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 relative z-10">
          {pillars.map((p, i) => {
            const Icon = p.icon
            return (
              <motion.div
                key={p.title}
                className="group relative rounded-xl border border-border bg-card p-6
                           hover:border-primary/30 transition-all duration-300
                           hover:shadow-lg hover:shadow-primary/5"
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ delay: i * 0.08, duration: 0.4 }}
              >
                {/* Gradient accent on hover */}
                <div
                  className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                  style={{
                    background: `radial-gradient(ellipse at top left, ${p.color}08, transparent 70%)`,
                  }}
                />
                <div className="relative z-10">
                  <div
                    className="w-11 h-11 rounded-lg flex items-center justify-center mb-4"
                    style={{ backgroundColor: `${p.color}15`, color: p.color }}
                  >
                    <Icon size={22} />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{p.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {p.desc}
                  </p>
                </div>
              </motion.div>
            )
          })}

          {/* 6th card: CTA */}
          <motion.div
            className="rounded-xl border border-dashed border-primary/30 bg-primary/5 p-6
                       flex flex-col items-center justify-center text-center"
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ delay: 0.4, duration: 0.4 }}
          >
            <div className="text-2xl font-bold text-primary mb-2">+</div>
            <p className="text-sm text-muted-foreground mb-4">
              And it all connects in one closed loop.
            </p>
            <Link
              to="/dashboard"
              className="text-xs font-semibold text-primary hover:text-primary/80 flex items-center gap-1"
            >
              Explore the platform <ArrowRight size={12} />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  COMPARISON TABLE                                            */}
      {/* ============================================================ */}
      <section className="px-6 py-24 max-w-5xl mx-auto">
        <motion.div
          className="text-center mb-12"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-3xl md:text-4xl font-bold mb-3">
            Why Pulsar AI?
          </h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            The only platform that unifies the entire LLM lifecycle.
          </p>
        </motion.div>

        <motion.div
          className="overflow-x-auto rounded-xl border border-border"
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-card border-b border-border">
                <th className="text-left px-5 py-3.5 font-medium text-muted-foreground">
                  Feature
                </th>
                <th className="px-5 py-3.5 font-semibold text-primary">
                  Pulsar AI
                </th>
                <th className="px-5 py-3.5 font-medium text-muted-foreground">
                  OpenJarvis
                </th>
                <th className="px-5 py-3.5 font-medium text-muted-foreground">
                  ClearML
                </th>
                <th className="px-5 py-3.5 font-medium text-muted-foreground">
                  W&B
                </th>
                <th className="px-5 py-3.5 font-medium text-muted-foreground">
                  LangSmith
                </th>
              </tr>
            </thead>
            <tbody>
              {comparisonData.map((row, i) => (
                <tr
                  key={row.feature}
                  className={`border-b border-border/50 ${
                    i % 2 === 0 ? "bg-card/50" : ""
                  }`}
                >
                  <td className="px-5 py-3 font-medium">{row.feature}</td>
                  <td className="px-5 py-3 text-center">
                    <CellMark ok={row.pulsar} highlight />
                  </td>
                  <td className="px-5 py-3 text-center">
                    <CellMark ok={row.openjarvis} />
                  </td>
                  <td className="px-5 py-3 text-center">
                    <CellMark ok={row.clearml} />
                  </td>
                  <td className="px-5 py-3 text-center">
                    <CellMark ok={row.wandb} />
                  </td>
                  <td className="px-5 py-3 text-center">
                    <CellMark ok={row.langsmith} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </motion.div>
      </section>

      {/* ============================================================ */}
      {/*  ARCHITECTURE DIAGRAM                                        */}
      {/* ============================================================ */}
      <section className="px-6 py-24 max-w-5xl mx-auto">
        <motion.div
          className="text-center mb-12"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-3xl md:text-4xl font-bold mb-3">Architecture</h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            A unified platform with clean separation of concerns.
          </p>
        </motion.div>

        <motion.div
          className="rounded-xl border border-border bg-card p-8 font-mono text-xs md:text-sm
                     leading-relaxed text-muted-foreground overflow-x-auto"
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <ArchitectureSvg />
        </motion.div>
      </section>

      {/* ============================================================ */}
      {/*  QUICK START                                                 */}
      {/* ============================================================ */}
      <section className="px-6 py-24 max-w-3xl mx-auto">
        <motion.div
          className="text-center mb-12"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-3xl md:text-4xl font-bold mb-3">Quick Start</h2>
          <p className="text-muted-foreground">Up and running in 30 seconds.</p>
        </motion.div>

        <motion.div
          className="relative rounded-xl border border-border bg-card overflow-hidden"
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          {/* Terminal chrome bar */}
          <div className="flex items-center gap-1.5 px-4 py-2.5 bg-secondary/50 border-b border-border">
            <div className="w-2.5 h-2.5 rounded-full bg-destructive/60" />
            <div className="w-2.5 h-2.5 rounded-full bg-warning/60" />
            <div className="w-2.5 h-2.5 rounded-full bg-success/60" />
            <span className="ml-2 text-[10px] text-muted-foreground/60 font-mono">
              terminal
            </span>
          </div>
          <div className="p-6 font-mono text-sm">
            <CopyButton text={"docker compose up"} />
            <div className="flex items-center gap-2 mb-1">
              <span className="text-success">$</span>
              <span className="text-foreground">docker compose up</span>
            </div>
            <div className="text-muted-foreground/60 mt-3 mb-1">
              # Open your browser at:
            </div>
            <div className="flex items-center gap-2">
              <span className="text-primary">
                {"-->"}
              </span>
              <a
                href="http://localhost:8888"
                className="text-primary hover:underline"
              >
                http://localhost:8888
              </a>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ============================================================ */}
      {/*  FOOTER                                                      */}
      {/* ============================================================ */}
      <footer className="border-t border-border py-8 px-6">
        <div className="max-w-5xl mx-auto flex items-center justify-between text-sm text-muted-foreground">
          <div>
            <span className="font-semibold text-foreground">Pulsar AI</span>
            {" "}&mdash; Apache 2.0
          </div>
          <a
            href="https://github.com/pulsar-ai/pulsar"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
            aria-label="GitHub"
          >
            <Github size={18} />
          </a>
        </div>
      </footer>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Cell mark for comparison table                                     */
/* ------------------------------------------------------------------ */

function CellMark({ ok, highlight = false }: { ok: boolean; highlight?: boolean }) {
  if (ok) {
    return (
      <span className={highlight ? "text-success font-bold text-base" : "text-success/70"}>
        {"\u2713"}
      </span>
    )
  }
  return <span className="text-muted-foreground/30">{"\u2717"}</span>
}

/* ------------------------------------------------------------------ */
/*  Architecture SVG diagram                                           */
/* ------------------------------------------------------------------ */

function ArchitectureSvg() {
  const boxW = 130
  const boxH = 42
  const gap = 16

  const layers = [
    {
      y: 0,
      label: "UI Layer",
      boxes: ["React SPA", "Workflow Editor", "Monitoring"],
      color: "#6d5dfc",
    },
    {
      y: 80,
      label: "API Layer",
      boxes: ["FastAPI", "WebSocket", "Auth"],
      color: "#3b82f6",
    },
    {
      y: 160,
      label: "Engine Layer",
      boxes: ["Training Engine", "DAG Runner", "Agent Runtime"],
      color: "#22c55e",
    },
    {
      y: 240,
      label: "Data Layer",
      boxes: ["SQLite", "File Storage", "Model Registry"],
      color: "#f59e0b",
    },
  ]

  const totalW = 3 * boxW + 2 * gap
  const svgW = totalW + 140
  const svgH = layers[layers.length - 1].y + boxH + 20

  return (
    <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full max-w-2xl mx-auto" style={{ minHeight: 280 }}>
      {layers.map((layer) => {
        const startX = 120
        return (
          <g key={layer.label}>
            {/* Layer label */}
            <text
              x={8}
              y={layer.y + boxH / 2 + 4}
              fill={layer.color}
              fontSize="11"
              fontWeight="600"
            >
              {layer.label}
            </text>
            {/* Boxes */}
            {layer.boxes.map((box, bi) => {
              const bx = startX + bi * (boxW + gap)
              return (
                <g key={box}>
                  <rect
                    x={bx}
                    y={layer.y}
                    width={boxW}
                    height={boxH}
                    rx={6}
                    fill={`${layer.color}10`}
                    stroke={layer.color}
                    strokeWidth="1"
                    strokeOpacity="0.3"
                  />
                  <text
                    x={bx + boxW / 2}
                    y={layer.y + boxH / 2 + 4}
                    textAnchor="middle"
                    fill="#fafafa"
                    fontSize="11"
                  >
                    {box}
                  </text>
                </g>
              )
            })}
            {/* Connecting arrows to next layer */}
            {layer.y < layers[layers.length - 1].y && (
              <line
                x1={startX + totalW / 2}
                y1={layer.y + boxH}
                x2={startX + totalW / 2}
                y2={layer.y + 80}
                stroke="#27272a"
                strokeWidth="1"
                strokeDasharray="4 3"
                markerEnd="url(#arrowhead)"
              />
            )}
          </g>
        )
      })}
      {/* Arrowhead marker */}
      <defs>
        <marker
          id="arrowhead"
          markerWidth="6"
          markerHeight="6"
          refX="6"
          refY="3"
          orient="auto"
        >
          <path d="M0,0 L6,3 L0,6" fill="#27272a" />
        </marker>
      </defs>
    </svg>
  )
}
