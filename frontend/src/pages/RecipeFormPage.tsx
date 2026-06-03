import { useEffect, useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { X } from "lucide-react"

import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/PageHeader"
import { cn } from "@/lib/utils"

interface FormState {
  title: string
  instructions: string
  servings: number
  image_url: string
  source_url: string
  source_domain: string
}

interface IngredientRow {
  key: string
  ingredientId: number | null
  ingredientName: string
  query: string
  quantity: string
  unit: string
  suggestedIngredientId: number | null
  confidence: number
  raw: string
}

interface Ingredient {
  id: number
  name: string
}

interface RecipeIngredientPayload {
  ingredient_id: number
  quantity: number
  unit: string
  order_index: number
}

interface LearnedAliasPayload {
  alias_name: string
  ingredient_id: number
}

interface Tag {
  id: number
  name: string
  group: string
  household_id: number | null
}

interface ScrapedIngredientItem {
  raw: string
  name: string
  quantity: number | null
  unit: string | null
  ingredient_id: number | null
  confidence: number
}

interface ScrapedRecipe {
  title: string
  ingredients: ScrapedIngredientItem[]
  instructions: string
  image_url: string | null
  servings: number
  source_url: string
  source_domain: string
  existing_recipe_id: number | null
  is_partial: boolean
}

const INITIAL_STATE: FormState = {
  title: "",
  instructions: "",
  servings: 4,
  image_url: "",
  source_url: "",
  source_domain: "",
}

const UNITS = ["g", "kg", "ml", "l", "EL", "TL", "Stück", "Bund", "Prise"]
const INGREDIENT_DEBOUNCE_MS = 200

let rowIdCounter = 0
function newRow(): IngredientRow {
  rowIdCounter += 1
  return {
    key: `row-${rowIdCounter}`,
    ingredientId: null,
    ingredientName: "",
    query: "",
    quantity: "",
    unit: "g",
    suggestedIngredientId: null,
    confidence: 0,
    raw: "",
  }
}

function IngredientCombobox({
  row,
  onChange,
}: {
  row: IngredientRow
  onChange: (row: IngredientRow) => void
}) {
  const [results, setResults] = useState<Ingredient[]>([])
  const [manuallyClosed, setManuallyClosed] = useState(false)
  const locked = row.ingredientId !== null

  useEffect(() => {
    if (locked) return
    const query = row.query.trim()
    if (query === "") return
    const controller = new AbortController()
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/ingredients?q=${encodeURIComponent(query)}`,
          {
            credentials: "same-origin",
            signal: controller.signal,
          }
        )
        if (!res.ok) return
        const data = (await res.json()) as Ingredient[]
        if (!controller.signal.aborted) {
          setResults(data)
        }
      } catch {
        // aborted or network error — ignore
      }
    }, INGREDIENT_DEBOUNCE_MS)
    return () => {
      clearTimeout(t)
      controller.abort()
    }
  }, [row.query, locked])

  const showDropdown =
    !locked &&
    row.query.trim() !== "" &&
    !manuallyClosed &&
    results.length > 0

  if (locked) {
    return (
      <div className="flex-1 flex flex-col gap-0.5">
        <div className="flex items-center gap-1">
          <span
            aria-label="Zutat"
            className="flex-1 truncate rounded-md border border-input bg-muted px-2.5 py-1 text-sm"
          >
            {row.ingredientName}
          </span>
          <button
            type="button"
            aria-label="Zutat ändern"
            className="inline-flex items-center justify-center rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground shrink-0"
            onClick={() => {
              onChange({
                ...row,
                ingredientId: null,
                ingredientName: "",
                query: row.ingredientName,
                suggestedIngredientId: null,
                confidence: 0,
              })
            }}
          >
            ↻
          </button>
        </div>
        {row.raw && (
          <span className="text-xs text-muted-foreground truncate">{row.raw}</span>
        )}
      </div>
    )
  }

  return (
    <div className="relative flex-1 flex flex-col gap-0.5">
      <Input
        type="text"
        role="combobox"
        value={row.query}
        placeholder="Zutat suchen..."
        aria-label="Zutat"
        aria-autocomplete="list"
        aria-expanded={showDropdown}
        aria-controls={`ingredient-list-${row.key}`}
        className="w-full"
        onChange={(e) => {
          setResults([])
          setManuallyClosed(false)
          onChange({ ...row, query: e.target.value, suggestedIngredientId: null })
        }}
        onFocus={() => setManuallyClosed(false)}
        onBlur={() => setManuallyClosed(true)}
      />
      {row.raw && (
        <span className="text-xs text-muted-foreground truncate">{row.raw}</span>
      )}
      {showDropdown && (
        <ul
          id={`ingredient-list-${row.key}`}
          role="listbox"
          className="absolute z-10 mt-1 max-h-40 w-full overflow-auto rounded-md border bg-popover shadow"
        >
          {results.map((ing) => (
            <li
              key={ing.id}
              role="option"
              aria-selected={ing.id === row.suggestedIngredientId}
              tabIndex={0}
              onMouseDown={(e) => {
                e.preventDefault()
                onChange({
                  ...row,
                  ingredientId: ing.id,
                  ingredientName: ing.name,
                  query: "",
                  suggestedIngredientId: null,
                })
              }}
              className={cn(
                "cursor-pointer px-2.5 py-1 text-sm hover:bg-muted",
                ing.id === row.suggestedIngredientId && "bg-muted font-medium"
              )}
            >
              {ing.name}
            </li>
          ))}
          {row.suggestedIngredientId !== null && (
            <li
              role="option"
              tabIndex={0}
              onMouseDown={(e) => {
                e.preventDefault()
                onChange({
                  ...row,
                  suggestedIngredientId: null,
                })
              }}
              className="cursor-pointer px-2.5 py-1 text-sm text-muted-foreground border-t hover:bg-muted"
            >
              Anderer Vorschlag…
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

class DuplicateRecipeError extends Error {
  existingRecipeId: number
  constructor(detail: string, existingRecipeId: number) {
    super(detail)
    this.existingRecipeId = existingRecipeId
    this.name = "DuplicateRecipeError"
  }
}

async function postRecipe(body: {
  title: string
  instructions: string
  servings: number
  image_url: string | null
  source_url: string | null
  source_domain: string | null
  ingredients: RecipeIngredientPayload[]
  learned_aliases: LearnedAliasPayload[]
}): Promise<{ id: number }> {
  const res = await fetch("/api/recipes", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Request failed" }))
    if (res.status === 409 && data.existing_recipe_id !== undefined) {
      throw new DuplicateRecipeError(
        data.detail || "Request failed",
        data.existing_recipe_id
      )
    }
    throw new Error(data.detail || "Request failed")
  }
  return res.json() as Promise<{ id: number }>
}

async function putRecipeTags(
  recipeId: number,
  tagIds: number[]
): Promise<void> {
  const res = await fetch(`/api/recipes/${recipeId}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag_ids: tagIds }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Request failed" }))
    throw new Error(data.detail || "Request failed")
  }
}

async function postRecipeImport(url: string): Promise<ScrapedRecipe> {
  const res = await fetch("/api/recipes/import", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Request failed" }))
    throw new Error(data.detail || "Request failed")
  }
  return res.json() as Promise<ScrapedRecipe>
}

function toNull(value: string): string | null {
  return value.trim() === "" ? null : value
}

function parseQuantity(value: string): number {
  const n = parseFloat(value)
  return Number.isFinite(n) ? n : 0
}

export default function RecipeFormPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const importUrl = searchParams.get("url")
  const [form, setForm] = useState<FormState>(INITIAL_STATE)
  const [rows, setRows] = useState<IngredientRow[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importedFrom, setImportedFrom] = useState<string | null>(null)
  const [isPartialImport, setIsPartialImport] = useState(false)
  const [existingRecipeId, setExistingRecipeId] = useState<number | null>(null)
  const [duplicateBlocked, setDuplicateBlocked] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function loadTags() {
      const res = await fetch("/api/tags", { credentials: "same-origin" })
      if (!res.ok) return
      const data = (await res.json()) as Tag[]
      if (!cancelled) setTags(data)
    }
    loadTags()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!importUrl) return
    const url = importUrl
    let cancelled = false
    async function runImport() {
      try {
        const data = await postRecipeImport(url)
        if (cancelled) return
        setForm({
          title: data.title,
          instructions: data.instructions,
          servings: data.servings,
          image_url: data.image_url ?? "",
          source_url: data.source_url,
          source_domain: data.source_domain,
        })
        setImportedFrom(data.source_domain)
        setIsPartialImport(data.is_partial)
        setExistingRecipeId(data.existing_recipe_id ?? null)
        setError(null)
        const importedRows: IngredientRow[] = data.ingredients.map(
          (item, idx) => {
            const isLocked =
              item.confidence >= 1.0 && item.ingredient_id !== null
            return {
              key: `import-${idx}`,
              ingredientId: isLocked ? (item.ingredient_id as number) : null,
              ingredientName: isLocked ? item.name : "",
              query: isLocked ? "" : (item.raw || item.name),
              quantity: item.quantity !== null ? String(item.quantity) : "",
              unit: item.unit || "g",
              suggestedIngredientId:
                !isLocked && item.ingredient_id !== null
                  ? (item.ingredient_id as number)
                  : null,
              confidence: item.confidence,
              raw: item.raw,
            }
          }
        )
        setRows(importedRows)
      } catch (err) {
        if (cancelled) return
        setError(
          err instanceof Error
            ? err.message
            : "Import fehlgeschlagen"
        )
      }
    }
    runImport()
    return () => {
      cancelled = true
    }
  }, [importUrl])

  const handleDiscardImport = () => {
    setForm(INITIAL_STATE)
    setImportedFrom(null)
    setIsPartialImport(false)
    setExistingRecipeId(null)
    setDuplicateBlocked(false)
    setError(null)
    setRows([])
    setSelectedTagIds([])
    const next = new URLSearchParams(searchParams)
    next.delete("url")
    setSearchParams(next, { replace: true })
  }

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    if (key === "source_url") {
      setDuplicateBlocked(false)
    }
  }

  const addRow = () => setRows((prev) => [...prev, newRow()])
  const updateRow = (idx: number, row: IngredientRow) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? row : r)))
  const removeRow = (idx: number) =>
    setRows((prev) => prev.filter((_, i) => i !== idx))

  const canSubmit =
    form.title.trim() !== "" &&
    form.instructions.trim() !== "" &&
    !submitting &&
    !duplicateBlocked

  const handleSourceUrlBlur = () => {
    if (form.source_url.trim() === "") return
    if (form.source_domain.trim() !== "") return
    try {
      const hostname = new URL(form.source_url.trim()).hostname
      update("source_domain", hostname)
    } catch {
      // ignore invalid URL
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const ingredients: RecipeIngredientPayload[] = rows
        .filter((r) => r.ingredientId !== null)
        .map((r, idx) => ({
          ingredient_id: r.ingredientId as number,
          quantity: parseQuantity(r.quantity),
          unit: r.unit,
          order_index: idx,
        }))
      const learnedAliases: LearnedAliasPayload[] = rows
        .filter(
          (r) =>
            r.ingredientId !== null &&
            r.confidence < 1.0 &&
            r.raw.trim() !== ""
        )
        .map((r) => ({
          alias_name: r.raw,
          ingredient_id: r.ingredientId as number,
        }))
      const created = await postRecipe({
        title: form.title.trim(),
        instructions: form.instructions.trim(),
        servings: form.servings,
        image_url: toNull(form.image_url),
        source_url: toNull(form.source_url),
        source_domain: toNull(form.source_domain),
        ingredients,
        learned_aliases: learnedAliases,
      })
      if (selectedTagIds.length > 0) {
        try {
          await putRecipeTags(created.id, selectedTagIds)
        } catch (putErr) {
          setError(
            putErr instanceof Error
              ? putErr.message
              : "Tags konnten nicht gespeichert werden"
          )
          setSubmitting(false)
          return
        }
      }
      navigate(`/recipes/${created.id}`)
    } catch (err) {
      if (err instanceof DuplicateRecipeError) {
        setExistingRecipeId(err.existingRecipeId)
        setDuplicateBlocked(true)
        setError(err.message)
      } else {
        setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen")
      }
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader title="Neues Rezept" />

      <form
        onSubmit={handleSubmit}
        className="mx-auto max-w-2xl space-y-4 rounded-lg border bg-card p-6"
      >
        {error && (
          <div
            role="alert"
            className="rounded-md bg-destructive/10 p-3 text-sm text-destructive"
          >
            {duplicateBlocked && existingRecipeId !== null ? (
              <>
                <p className="font-medium">
                  Du hast dieses Rezept schon importiert
                </p>
                <Link
                  to={`/recipes/${existingRecipeId}`}
                  className="text-xs underline"
                >
                  Zum bestehenden Rezept
                </Link>
              </>
            ) : (
              error
            )}
          </div>
        )}

        {importedFrom && existingRecipeId !== null && (
          <div
            role="status"
            className={cn(
              "flex items-center justify-between rounded-md p-3 text-sm",
              "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
            )}
          >
            <div>
              <p className="font-medium">
                Du hast dieses Rezept schon importiert
              </p>
              <Link
                to={`/recipes/${existingRecipeId}`}
                className="text-xs underline"
              >
                Zum bestehenden Rezept
              </Link>
            </div>
          </div>
        )}

        {importedFrom && (
          <div
            role="status"
            className={cn(
              "flex items-center justify-between rounded-md p-3 text-sm",
              isPartialImport
                ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                : "bg-muted"
            )}
          >
            <div>
              {isPartialImport ? (
                <>
                  <p className="font-medium">Teilimport — bitte vervollständigen</p>
                  <p className="text-xs opacity-80">Bitte Zutaten und Zubereitung ergänzen</p>
                </>
              ) : (
                <span>Importiert von {importedFrom}</span>
              )}
            </div>
            <button
              type="button"
              onClick={handleDiscardImport}
              className="rounded-md px-2 py-1 text-sm underline-offset-2 hover:underline"
            >
              Verwerfen
            </button>
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="recipe-title" className="text-sm font-medium">
            Titel
          </label>
          <Input
            id="recipe-title"
            type="text"
            value={form.title}
            onChange={(e) => update("title", e.target.value)}
            required
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-instructions" className="text-sm font-medium">
            Zubereitung
          </label>
          <textarea
            id="recipe-instructions"
            value={form.instructions}
            onChange={(e) => update("instructions", e.target.value)}
            rows={6}
            required
            className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-servings" className="text-sm font-medium">
            Portionen
          </label>
          <Input
            id="recipe-servings"
            type="number"
            min={1}
            value={form.servings}
            onChange={(e) =>
              update("servings", Math.max(1, Number(e.target.value) || 1))
            }
            required
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-image-url" className="text-sm font-medium">
            Bild-URL
          </label>
          <Input
            id="recipe-image-url"
            type="url"
            value={form.image_url}
            onChange={(e) => update("image_url", e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-source-url" className="text-sm font-medium">
            Quelle
          </label>
          <Input
            id="recipe-source-url"
            type="url"
            value={form.source_url}
            onChange={(e) => update("source_url", e.target.value)}
            onBlur={handleSourceUrlBlur}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-source-domain" className="text-sm font-medium">
            Quell-Domain
          </label>
          <Input
            id="recipe-source-domain"
            type="text"
            value={form.source_domain}
            onChange={(e) => update("source_domain", e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <h2 className="text-sm font-medium">Tags</h2>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => {
              const isActive = selectedTagIds.includes(tag.id)
              return (
                <button
                  key={tag.id}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() =>
                    setSelectedTagIds((prev) =>
                      prev.includes(tag.id)
                        ? prev.filter((id) => id !== tag.id)
                        : [...prev, tag.id]
                    )
                  }
                  className={cn(
                    "cursor-pointer rounded-full px-3 py-1 text-sm transition",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted hover:bg-muted-foreground/20"
                  )}
                >
                  {tag.name}
                </button>
              )
            })}
          </div>
        </div>

        <div className="space-y-2">
          <h2 className="text-sm font-medium">Zutaten</h2>
          <div className="space-y-2">
            {rows.map((row, idx) => (
              <div key={row.key} className="flex items-center gap-2">
                <IngredientCombobox
                  row={row}
                  onChange={(r) => updateRow(idx, r)}
                />
                <Input
                  type="number"
                  step="any"
                  min="0"
                  value={row.quantity}
                  placeholder="Menge"
                  aria-label="Menge"
                  className="w-20"
                  onChange={(e) =>
                    updateRow(idx, { ...row, quantity: e.target.value })
                  }
                />
                <select
                  aria-label="Einheit"
                  value={row.unit}
                  onChange={(e) =>
                    updateRow(idx, { ...row, unit: e.target.value })
                  }
                  className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
                >
                  {UNITS.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Zutat entfernen"
                  onClick={() => removeRow(idx)}
                >
                  <X />
                </Button>
              </div>
            ))}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addRow}
          >
            + Zutat hinzufügen
          </Button>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2">
          <Link
            to="/recipes"
            className={buttonVariants({ variant: "ghost" })}
          >
            Abbrechen
          </Link>
          <Button type="submit" disabled={!canSubmit}>
            {submitting ? "Wird gespeichert..." : "Speichern"}
          </Button>
        </div>
      </form>
    </div>
  )
}
