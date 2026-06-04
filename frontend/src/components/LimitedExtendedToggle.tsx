import { cn } from "@/lib/utils"

export interface LimitedExtendedToggleProps {
  mode: "simple" | "extended"
  onChange: (mode: "simple" | "extended") => void
}

export function LimitedExtendedToggle({
  mode,
  onChange,
}: LimitedExtendedToggleProps) {
  return (
    <div className="inline-flex rounded-lg border bg-muted p-0.5">
      <button
        type="button"
        onClick={() => onChange("simple")}
        className={cn(
          "cursor-pointer rounded-md px-3 py-1 text-sm font-medium transition",
          mode === "simple"
            ? "bg-background shadow-sm"
            : "text-muted-foreground"
        )}
      >
        Einfach
      </button>
      <button
        type="button"
        onClick={() => onChange("extended")}
        className={cn(
          "cursor-pointer rounded-md px-3 py-1 text-sm font-medium transition",
          mode === "extended"
            ? "bg-background shadow-sm"
            : "text-muted-foreground"
        )}
      >
        Erweitert
      </button>
    </div>
  )
}
