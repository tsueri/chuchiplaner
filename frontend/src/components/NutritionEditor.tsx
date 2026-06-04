import { Input } from "@/components/ui/input"
import { NUTRITION_FIELDS } from "./NutritionEditor.types"

export interface NutritionEditorProps {
  nutrition: Record<string, string>
  onChange: (nutrition: Record<string, string>) => void
}

export function NutritionEditor({ nutrition, onChange }: NutritionEditorProps) {
  const update = (key: string, raw: string) => {
    const next = { ...nutrition }
    if (raw.trim() === "") {
      delete next[key]
    } else {
      next[key] = raw
    }
    onChange(next)
  }

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium">Nährwerte</h2>
      <div className="grid grid-cols-3 gap-2">
        {NUTRITION_FIELDS.map((field) => {
          const value = nutrition[field.key] ?? ""
          return (
            <div key={field.key} className="flex items-center gap-1">
              <Input
                id={`nutrition-${field.key}`}
                type="text"
                inputMode="decimal"
                value={value}
                onChange={(e) => update(field.key, e.target.value)}
                aria-label={field.label}
                placeholder={field.label}
                className="h-8 text-xs"
              />
              <span className="shrink-0 text-xs text-muted-foreground">
                {field.unit}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function parseNutrition(nutrition: Record<string, string>): Record<string, number> {
  const result: Record<string, number> = {}
  for (const [key, raw] of Object.entries(nutrition)) {
    const trimmed = raw.trim()
    if (trimmed === "") continue
    const num = parseFloat(trimmed.replace(",", "."))
    if (Number.isFinite(num)) {
      result[key] = num
    }
  }
  return result
}

export function nutritionFromApi(
  apiNutrition: Record<string, unknown> | null | undefined
): Record<string, string> {
  if (!apiNutrition) return {}
  const result: Record<string, string> = {}
  for (const [key, val] of Object.entries(apiNutrition)) {
    if (typeof val === "number") {
      result[key] = String(val)
    } else if (
      val !== null &&
      val !== undefined &&
      typeof val === "object" &&
      !Array.isArray(val) &&
      "value" in val &&
      typeof (val as Record<string, unknown>).value === "number"
    ) {
      result[key] = String((val as Record<string, number>).value)
    }
  }
  return result
}
