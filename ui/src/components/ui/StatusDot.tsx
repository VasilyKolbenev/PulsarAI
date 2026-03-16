import { cn } from "@/lib/utils"

type StatusColor = "success" | "warning" | "error" | "info" | "muted"

interface StatusDotProps {
  status: StatusColor
  pulse?: boolean
  className?: string
  label?: string
}

const colors: Record<StatusColor, string> = {
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-destructive",
  info: "bg-primary",
  muted: "bg-muted-foreground",
}

export function StatusDot({ status, pulse, className, label }: StatusDotProps) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span className="relative flex h-2 w-2">
        {pulse && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              colors[status],
            )}
          />
        )}
        <span
          className={cn("relative inline-flex h-2 w-2 rounded-full", colors[status])}
        />
      </span>
      {label && <span className="text-xs text-muted-foreground">{label}</span>}
    </span>
  )
}
