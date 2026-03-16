import { useEffect, useState, useCallback } from "react"
import { useDropzone } from "react-dropzone"
import { api } from "@/api/client"
import { Upload, Trash2, Eye, Database } from "lucide-react"
import { EmptyState } from "@/components/ui/EmptyState"
import { Breadcrumbs } from "@/components/ui/Breadcrumbs"

export function Datasets() {
  const [datasets, setDatasets] = useState<Array<Record<string, unknown>>>([])
  const [preview, setPreview] = useState<{
    columns: string[]
    rows: Array<Record<string, unknown>>
    total_rows: number
  } | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    api.getDatasets().then(setDatasets).catch(() => {})
  }

  useEffect(load, [])

  const onDrop = useCallback(async (files: File[]) => {
    if (files.length === 0) return
    setUploading(true)
    setError(null)
    try {
      await api.uploadDataset(files[0])
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/json": [".jsonl"],
      "application/octet-stream": [".parquet"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    },
    maxFiles: 1,
  })

  const handlePreview = async (id: string) => {
    try {
      const res = await api.previewDataset(id)
      setPreview(res)
    } catch {
      // ignore
    }
  }

  const handleDelete = async (id: string) => {
    await api.deleteDataset(id)
    if (preview) setPreview(null)
    load()
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Dashboard", href: "/dashboard" }, { label: "Datasets" }]} />
      <div>
        <h2 className="text-2xl font-bold">Datasets</h2>
        <p className="text-muted-foreground text-sm mt-1">Upload and manage training data</p>
      </div>

      {/* Upload zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-muted-foreground"
        }`}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto mb-3 text-muted-foreground" size={32} />
        {uploading ? (
          <p className="text-sm text-muted-foreground">Uploading...</p>
        ) : isDragActive ? (
          <p className="text-sm text-primary">Drop your file here</p>
        ) : (
          <>
            <p className="text-sm">Drag & drop a dataset file, or click to browse</p>
            <p className="text-xs text-muted-foreground mt-1">CSV, JSONL, Parquet, Excel</p>
          </>
        )}
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {/* Datasets list */}
      {datasets.length === 0 && !uploading && (
        <EmptyState
          icon={Database}
          title="No datasets uploaded"
          description="Upload a CSV, JSONL, Parquet, or Excel file to get started with training."
        />
      )}
      {datasets.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-secondary/50">
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Format</th>
                <th className="text-left px-4 py-2 font-medium">Rows</th>
                <th className="text-left px-4 py-2 font-medium">Size</th>
                <th className="w-20 px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={String(d.id)} className="border-t border-border hover:bg-secondary/30">
                  <td className="px-4 py-2">{String(d.name)}</td>
                  <td className="px-4 py-2 text-muted-foreground">{String(d.format).toUpperCase()}</td>
                  <td className="px-4 py-2 font-mono">{String(d.num_rows)}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {((Number(d.size_bytes) || 0) / 1024).toFixed(1)} KB
                  </td>
                  <td className="px-3 py-2 flex gap-2">
                    <button
                      onClick={() => handlePreview(String(d.id))}
                      className="text-primary hover:text-primary/80"
                    >
                      <Eye size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(String(d.id))}
                      className="text-destructive hover:text-destructive/80"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Preview */}
      {preview && (
        <div className="bg-card border border-border rounded-lg p-4 space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="font-semibold">Preview ({preview.total_rows} rows total)</h3>
            <button onClick={() => setPreview(null)} className="text-muted-foreground text-sm hover:text-foreground">
              Close
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-secondary/50">
                  {preview.columns.map((col) => (
                    <th key={col} className="text-left px-3 py-1.5 font-medium">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-t border-border">
                    {preview.columns.map((col) => (
                      <td key={col} className="px-3 py-1.5 max-w-48 truncate">
                        {String(row[col] ?? "")}
                      </td>
                    ))}
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
