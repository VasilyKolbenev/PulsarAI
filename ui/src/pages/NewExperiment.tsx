import { useState, useEffect } from "react"
import { api } from "@/api/client"
import { useSSE } from "@/hooks/useSSE"
import { LossChart } from "@/components/training/LossChart"
import { ModelSelector } from "@/components/ui/ModelSelector"

export function NewExperiment() {
  const [step, setStep] = useState(0)
  const [name, setName] = useState("")
  const [task, setTask] = useState("sft")
  const [model, setModel] = useState("Qwen/Qwen2.5-3B-Instruct")
  const [datasetId, setDatasetId] = useState("")
  const [datasetPath, setDatasetPath] = useState("")
  const [lr, setLr] = useState("2e-4")
  const [epochs, setEpochs] = useState("3")
  const [batchSize, setBatchSize] = useState("1")
  const [gradAccum, setGradAccum] = useState("16")
  const [maxSeqLen, setMaxSeqLen] = useState("512")

  const [datasets, setDatasets] = useState<Array<Record<string, unknown>>>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const sse = useSSE(jobId)

  useEffect(() => {
    api.getDatasets().then(setDatasets).catch(() => {})
  }, [])

  const handleStart = async () => {
    setError(null)
    try {
      const config = {
        model: { name: model },
        dataset: { path: datasetPath },
        _dataset_id: datasetId,
        training: {
          learning_rate: parseFloat(lr),
          epochs: parseInt(epochs),
          batch_size: parseInt(batchSize),
          gradient_accumulation: parseInt(gradAccum),
          max_seq_length: parseInt(maxSeqLen),
        },
        output: { dir: `./outputs/${name}` },
      }
      const res = await api.startTraining({ name, config, task })
      setJobId(res.job_id)
      setStep(3)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start training")
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold">New Experiment</h2>
        <p className="text-muted-foreground text-sm mt-1">Configure and launch training</p>
      </div>

      {/* Step indicator */}
      <div className="flex gap-2">
        {["Setup", "Dataset", "Training", "Progress"].map((label, i) => (
          <div
            key={label}
            className={`flex-1 text-center text-xs py-1.5 rounded ${
              i === step
                ? "bg-primary text-primary-foreground font-medium"
                : i < step
                ? "bg-primary/20 text-primary"
                : "bg-secondary text-muted-foreground"
            }`}
          >
            {label}
          </div>
        ))}
      </div>

      {/* Step 0: Setup */}
      {step === 0 && (
        <div className="space-y-4">
          <Field label="Experiment Name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-classifier"
              className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-ring focus:outline-none"
            />
          </Field>
          <Field label="Task">
            <select
              value={task}
              onChange={(e) => setTask(e.target.value)}
              className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm"
            >
              <option value="sft">SFT (Supervised Fine-Tuning)</option>
              <option value="dpo">DPO (Direct Preference Optimization)</option>
            </select>
          </Field>
          <Field label="Base Model">
            <ModelSelector value={model} onChange={setModel} />
          </Field>
          <button
            onClick={() => setStep(1)}
            disabled={!name}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium disabled:opacity-50"
          >
            Next: Dataset
          </button>
        </div>
      )}

      {/* Step 1: Dataset */}
      {step === 1 && (
        <div className="space-y-4">
          <Field label="Select Dataset">
            <select
              value={datasetId}
              onChange={(e) => {
                setDatasetId(e.target.value)
                const ds = datasets.find((d) => d.id === e.target.value)
                if (ds) setDatasetPath(String(ds.path || ""))
              }}
              className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm"
            >
              <option value="">-- Select uploaded dataset --</option>
              {datasets.map((d) => (
                <option key={String(d.id)} value={String(d.id)}>
                  {String(d.name)} ({String(d.num_rows)} rows)
                </option>
              ))}
            </select>
          </Field>
          <p className="text-xs text-muted-foreground">
            Or enter path manually:
          </p>
          <input
            value={datasetPath}
            onChange={(e) => setDatasetPath(e.target.value)}
            placeholder="data/train.csv"
            className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-ring focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => setStep(0)}
              className="px-4 py-2 bg-secondary text-secondary-foreground rounded-md text-sm"
            >
              Back
            </button>
            <button
              onClick={() => setStep(2)}
              disabled={!datasetPath}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium disabled:opacity-50"
            >
              Next: Parameters
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Training params */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Learning Rate">
              <input value={lr} onChange={(e) => setLr(e.target.value)}
                className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm" />
            </Field>
            <Field label="Epochs">
              <input value={epochs} onChange={(e) => setEpochs(e.target.value)} type="number"
                className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm" />
            </Field>
            <Field label="Batch Size">
              <input value={batchSize} onChange={(e) => setBatchSize(e.target.value)} type="number"
                className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm" />
            </Field>
            <Field label="Gradient Accumulation">
              <input value={gradAccum} onChange={(e) => setGradAccum(e.target.value)} type="number"
                className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm" />
            </Field>
            <Field label="Max Seq Length">
              <input value={maxSeqLen} onChange={(e) => setMaxSeqLen(e.target.value)} type="number"
                className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm" />
            </Field>
          </div>
          {error && <p className="text-destructive text-sm">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={() => setStep(1)}
              className="px-4 py-2 bg-secondary text-secondary-foreground rounded-md text-sm"
            >
              Back
            </button>
            <button
              onClick={handleStart}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium"
            >
              Start Training
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Progress */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Status:</span>
            <span className={`text-sm font-medium ${
              sse.status === "completed" ? "text-success" :
              sse.status === "error" ? "text-destructive" :
              "text-warning"
            }`}>
              {sse.status}
            </span>
          </div>

          {sse.metrics.length > 0 && (
            <>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div className="bg-card border border-border rounded-md p-3">
                  <div className="text-muted-foreground text-xs">Step</div>
                  <div className="font-mono font-bold">{sse.metrics[sse.metrics.length - 1].step}</div>
                </div>
                <div className="bg-card border border-border rounded-md p-3">
                  <div className="text-muted-foreground text-xs">Loss</div>
                  <div className="font-mono font-bold">
                    {sse.metrics[sse.metrics.length - 1].loss?.toFixed(4) ?? "—"}
                  </div>
                </div>
                <div className="bg-card border border-border rounded-md p-3">
                  <div className="text-muted-foreground text-xs">Epoch</div>
                  <div className="font-mono font-bold">{sse.metrics[sse.metrics.length - 1].epoch}</div>
                </div>
              </div>
              <LossChart data={sse.metrics} />
            </>
          )}

          {sse.error && <p className="text-destructive text-sm">{sse.error}</p>}
        </div>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1.5">{label}</label>
      {children}
    </div>
  )
}
