import { cn } from "@/lib/utils"

interface DailyLimitIndicatorProps {
  capacity: number
  used: number
  remaining: number
  isLoading: boolean
  error?: Error | null
}

export function DailyLimitIndicator({
  capacity,
  used,
  remaining,
  isLoading,
  error,
}: DailyLimitIndicatorProps) {
  const isExceeded = remaining === 0 && capacity > 0

  const content = (() => {
    if (isLoading) return "--/--"
    if (error) return "?/?"
    if (!capacity) return "-/-"
    return `${used}/${capacity}`
  })()

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium bg-card/80 backdrop-blur",
        isExceeded
          ? "border-destructive/50 bg-destructive/10 text-destructive"
          : "border-border bg-background text-muted-foreground",
      )}
      aria-label="Daily worker limit"
    >
      <span className="uppercase tracking-wide">Today</span>
      <span className="h-3 w-px bg-border/60" />
      <span>{content}</span>
    </div>
  )
}

