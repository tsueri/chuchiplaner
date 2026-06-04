import { useEffect, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/PageHeader"

interface IngredientConv {
  id: number
  name: string
  grams_per_el: number | null
  ml_per_el: number | null
  grams_per_tl: number | null
  ml_per_tl: number | null
  grams_per_msp: number | null
  ml_per_msp: number | null
  grams_per_pris: number | null
  ml_per_pris: number | null
}

type SpoonUnit = "el" | "tl" | "msp" | "pris"
type MeasureType = "grams" | "ml"

interface EditingCell {
  ingredientId: number
  spoon: SpoonUnit
  field: MeasureType
}

const SPOON_COLUMNS: { spoon: SpoonUnit; label: string }[] = [
  { spoon: "el", label: "EL" },
  { spoon: "tl", label: "TL" },
  { spoon: "msp", label: "MSP" },
  { spoon: "pris", label: "Prise" },
]

function fieldName(spoon: SpoonUnit, measure: MeasureType): string {
  return `${measure}_per_${spoon}`
}

function getValue(
  ing: IngredientConv,
  spoon: SpoonUnit
): { value: number | null; measure: MeasureType | null } {
  const gramsField = fieldName(spoon, "grams") as keyof IngredientConv
  const mlField = fieldName(spoon, "ml") as keyof IngredientConv
  const gramsVal = ing[gramsField] as number | null
  const mlVal = ing[mlField] as number | null
  if (gramsVal !== null) return { value: gramsVal, measure: "grams" }
  if (mlVal !== null) return { value: mlVal, measure: "ml" }
  return { value: null, measure: null }
}

async function api(path: string, options?: RequestInit) {
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Request failed" }))
    throw new Error(data.detail || "Request failed")
  }
  if (res.status === 204) return null
  return res.json()
}

export default function IngredientsPage() {
  const [ingredients, setIngredients] = useState<IngredientConv[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [search, setSearch] = useState("")
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null)
  const [editValue, setEditValue] = useState("")
  const [newIngredientMode, setNewIngredientMode] = useState(false)
  const [newIngredientName, setNewIngredientName] = useState("")
  const [newIngredientSubmitting, setNewIngredientSubmitting] = useState(false)
  const [newIngredientError, setNewIngredientError] = useState("")
  const [cellError, setCellError] = useState<string | null>(null)

  useEffect(() => {
    api("/ingredients")
      .then((data: IngredientConv[]) => setIngredients(data))
      .catch(() => setError("Zutaten konnten nicht geladen werden"))
      .finally(() => setLoading(false))
  }, [])

  const filteredIngredients = search
    ? ingredients.filter((ing) =>
        ing.name.toLowerCase().includes(search.toLowerCase())
      )
    : ingredients

  const refreshIngredients = () => {
    api("/ingredients")
      .then((data: IngredientConv[]) => setIngredients(data))
      .catch(() => {})
  }

  const handleNewIngredient = async (e: FormEvent) => {
    e.preventDefault()
    const name = newIngredientName.trim()
    if (!name) return
    setNewIngredientError("")
    setNewIngredientSubmitting(true)
    try {
      await api("/ingredients", {
        method: "POST",
        body: JSON.stringify({ name }),
      })
      setNewIngredientName("")
      setNewIngredientMode(false)
      refreshIngredients()
    } catch (err) {
      setNewIngredientError(
        err instanceof Error ? err.message : "Erstellen fehlgeschlagen"
      )
    } finally {
      setNewIngredientSubmitting(false)
    }
  }

  const startEdit = (
    ing: IngredientConv,
    spoon: SpoonUnit,
    measure: MeasureType,
    currentValue: number | null
  ) => {
    setCellError(null)
    setEditingCell({ ingredientId: ing.id, spoon, field: measure })
    setEditValue(currentValue !== null ? String(currentValue) : "")
  }

  const commitEdit = async () => {
    if (!editingCell) return
    setCellError(null)
    const trimmed = editValue.trim()
    const field = fieldName(editingCell.spoon, editingCell.field)

    let body: Record<string, number | null>
    if (trimmed === "") {
      body = { [field]: null }
    } else {
      const num = parseFloat(trimmed)
      if (isNaN(num)) {
        setEditingCell(null)
        setEditValue("")
        return
      }
      body = { [field]: num }
    }

    try {
      const updated = await api(`/ingredients/${editingCell.ingredientId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      })
      setIngredients((prev) =>
        prev.map((ing) =>
          ing.id === updated.id ? (updated as IngredientConv) : ing
        )
      )
      setEditingCell(null)
      setEditValue("")
    } catch (err) {
      setCellError(
        err instanceof Error ? err.message : "Speichern fehlgeschlagen"
      )
    }
  }

  const cancelEdit = () => {
    setEditingCell(null)
    setEditValue("")
    setCellError(null)
  }

  const isEditingCell = (ingredientId: number, spoon: SpoonUnit): boolean => {
    return editingCell !== null && editingCell.ingredientId === ingredientId && editingCell.spoon === spoon
  }

  return (
    <div>
      <PageHeader
        title="Zutaten"
        actions={
          <Button onClick={() => setNewIngredientMode(!newIngredientMode)}>
            {newIngredientMode ? "Abbrechen" : "Neue Zutat"}
          </Button>
        }
      />

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* New ingredient form */}
      {newIngredientMode && (
        <form
          onSubmit={handleNewIngredient}
          className="mb-6 rounded-lg border p-4 space-y-3"
        >
          {newIngredientError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {newIngredientError}
            </div>
          )}
          <div className="flex items-center gap-2">
            <Input
              type="text"
              value={newIngredientName}
              onChange={(e) => setNewIngredientName(e.target.value)}
              placeholder="Name der Zutat"
              className="flex-1"
            />
            <Button type="submit" disabled={newIngredientSubmitting}>
              {newIngredientSubmitting ? "Wird erstellt..." : "Hinzufügen"}
            </Button>
          </div>
        </form>
      )}

      {loading && (
        <div className="p-4 text-muted-foreground">Laden...</div>
      )}

      {!loading && <>

      {/* Search */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="Zutaten suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm w-full max-w-sm"
        />
      </div>

      {/* Cell error */}
      {cellError && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {cellError}
        </div>
      )}

      {/* Ingredients table */}
      {filteredIngredients.length === 0 ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
          {search
            ? "Keine Zutaten gefunden."
            : "Keine Zutaten vorhanden."}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left px-4 py-3 font-medium">Name</th>
                {SPOON_COLUMNS.map(({ spoon, label }) => (
                  <th key={spoon} className="text-right px-4 py-3 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredIngredients.map((ing) => (
                <tr key={ing.id} className="border-b hover:bg-muted/30">
                  <td className="px-4 py-2.5 font-medium">{ing.name}</td>
                  {SPOON_COLUMNS.map(({ spoon }) => {
                    const { value, measure } = getValue(ing, spoon)
                    const editing = isEditingCell(ing.id, spoon)

                    if (editing) {
                      return (
                        <td key={spoon} className="px-2 py-1 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Input
                              type="number"
                              step="any"
                              min="0"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              onBlur={commitEdit}
                              onKeyDown={(e) => {
                                if (e.key === "Escape") cancelEdit()
                              }}
                              autoFocus
                              className="w-20 h-8 text-right text-sm"
                            />
                            <select
                              value={editingCell!.field}
                              onChange={(e) =>
                                setEditingCell({
                                  ...editingCell!,
                                  field: e.target.value as MeasureType,
                                })
                              }
                              className="h-8 rounded border bg-background px-1 text-xs"
                            >
                              <option value="grams">g</option>
                              <option value="ml">ml</option>
                            </select>
                          </div>
                        </td>
                      )
                    }

                    return (
                      <td
                        key={spoon}
                        className="px-4 py-2.5 text-right cursor-pointer hover:bg-muted/50"
                        onClick={() =>
                          startEdit(ing, spoon, measure ?? "grams", value)
                        }
                      >
                        {value !== null && measure !== null ? (
                          <span>
                            {value} {measure === "grams" ? "g" : "ml"}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      </>}
    </div>
  )
}
