import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Layout } from "@/components/layout/Layout"
import { Landing } from "@/pages/Landing"
import { Login } from "@/pages/Login"
import { AuthProvider } from "@/components/AuthProvider"
import { ToastContainer } from "@/components/ui/Toast"
import { lazy, Suspense } from "react"

// Lazy load heavy pages
const WorkflowBuilder = lazy(() =>
  import("@/pages/WorkflowBuilder").then((m) => ({ default: m.WorkflowBuilder }))
)
const PromptLab = lazy(() =>
  import("@/pages/PromptLab").then((m) => ({ default: m.PromptLab }))
)
const Monitoring = lazy(() =>
  import("@/pages/Monitoring").then((m) => ({ default: m.Monitoring }))
)

// Keep direct imports for lightweight pages
import { Dashboard } from "@/pages/Dashboard"
import { NewExperiment } from "@/pages/NewExperiment"
import { Experiments } from "@/pages/Experiments"
import { Datasets } from "@/pages/Datasets"
import { Compute } from "@/pages/Compute"
import { Agent } from "@/pages/Agent"
import { Settings } from "@/pages/Settings"

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <ToastContainer />
      <Suspense
        fallback={
          <div className="flex items-center justify-center h-screen text-muted-foreground">
            Loading...
          </div>
        }
      >
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/new" element={<NewExperiment />} />
            <Route path="/experiments" element={<Experiments />} />
            <Route path="/datasets" element={<Datasets />} />
            <Route path="/workflows" element={<WorkflowBuilder />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/compute" element={<Compute />} />
            <Route path="/prompts" element={<PromptLab />} />
            <Route path="/agent" element={<Agent />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </Suspense>
      </AuthProvider>
    </BrowserRouter>
  )
}
