import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { Card } from "./Card"

interface MetricCardProps {
  icon: LucideIcon
  label: string
  value: string | number
  subtext?: string
  trend?: "up" | "down" | "flat"
  className?: string
}

export function MetricCard({ icon: Icon, label, value, subtext, trend, className }: MetricCardProps) {
  return (
    <Card className={cn("flex items-start gap-3", className)}>
      <div className="rounded-lg bg-primary/10 p-2">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-xl font-semibold text-foreground mt-0.5">{value}</p>
        {subtext && (
          <p
            className={cn(
              "text-xs mt-0.5",
              trend === "up" && "text-success",
              trend === "down" && "text-destructive",
              !trend && "text-muted-foreground",
            )}
          >
            {subtext}
          </p>
        )}
      </div>
    </Card>
  )
}
