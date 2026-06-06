import { useEffect, useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"

import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { EditableIngredientRow } from "@/components/EditableIngredientRow"
import {
  defaultEditableIngredientValue,
  type EditableIngredientValue,
} from "@/components/EditableIngredientRow.types"
import { EditableStepRow } from "@/components/EditableStepRow"
import {
  defaultEditableStepValue,
  type EditableStepValue,
} from "@/components/EditableStepRow.types"
import { LimitedExtendedToggle } from "@/components/LimitedExtendedToggle"
import { PageHeader } from "@/components/PageHeader"
import { cn } from "@/lib/utils"
import { DurationSerializer } from "@/lib/duration-serializer"
import {
  NutritionEditor,
  parseNutrition,
  nutritionFromApi,
} from "@/components/NutritionEditor"

interface FormState {
  title: string
  description: string
  stepsText: string
  servings: number
  prepTimeText: string
  totalTimeText: string
  cookTimeText: string
  performTimeText: string
  author: string
  datePublished: string
  keywords: string
  nutritionText: Record<string, string>
  image_url: string
  source_url: string
  source_domain: string
}

type IngredientRow = EditableIngredientValue

interface RecipeIngredientPayload {
  ingredient_id: number
  quantity: number
  unit: string
  order_index: number
  suggested_ingredient_name: string | null
  original_name: string | null
}

interface RecipeStepPayload {
  position: number
  text: string
  name: string | null
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
  suggested_ingredient_name: string | null
}

interface ScrapedStepItem {
  position: number
  text: string
  name: string | null
}

interface ScrapedRecipe {
  title: string
  ingredients: ScrapedIngredientItem[]
  steps: ScrapedStepItem[]
  image_url: string | null
  servings: number
  source_url: string
  source_domain: string
  existing_recipe_id: number | null
  is_partial: boolean
  description: string | null
  prep_time_minutes: number | null
  cook_time_minutes: number | null
  total_time_minutes: number | null
  perform_time_minutes: number | null
  author: string | null
  date_published: string | null
  keywords: string | null
  ratings: number | null
  nutrients: Record<string, unknown> | null
  suitable_for_diet_tag_ids: number[]
}

const INITIAL_STATE: FormState = {
  title: "",
  description: "",
  stepsText: "",
  servings: 4,
  prepTimeText: "",
  totalTimeText: "",
  cookTimeText: "",
  performTimeText: "",
  author: "",
  datePublished: "",
  keywords: "",
  nutritionText: {},
  image_url: "",
  source_url: "",
  source_domain: "",
}

function newRow(): IngredientRow {
  return defaultEditableIngredientValue()
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
  description: string | null
  steps: RecipeStepPayload[]
  servings: number
  prep_time_minutes: number | null
  total_time_minutes: number | null
  cook_time_minutes: number | null
  perform_time_minutes: number | null
  author: string | null
  date_published: string | null
  keywords: string | null
  nutrition: Record<string, number> | null
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

async function putFullRecipe(
  recipeId: number,
  body: {
    title: string
    description: string | null
    steps: RecipeStepPayload[]
    servings: number
    prep_time_minutes: number | null
    total_time_minutes: number | null
    cook_time_minutes: number | null
    perform_time_minutes: number | null
    author: string | null
    date_published: string | null
    keywords: string | null
    nutrition: Record<string, number> | null
    image_url: string | null
    source_url: string | null
    source_domain: string | null
    ingredients: RecipeIngredientPayload[]
    tag_ids: number[]
  }
): Promise<void> {
  const res = await fetch(`/api/recipes/${recipeId}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Request failed" }))
    throw new Error(data.detail || "Request failed")
  }
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
  const [mode, setMode] = useState<"simple" | "extended">("simple")
  const [steps, setSteps] = useState<EditableStepValue[]>([])

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
        const stepsText = (data.steps ?? [])
          .sort((a, b) => a.position - b.position)
          .map((s) => s.text)
          .join("\n")
        setForm({
          title: data.title,
          description: data.description ?? "",
          stepsText,
          servings: data.servings,
          prepTimeText: data.prep_time_minutes !== null
            ? DurationSerializer.formatHuman(data.prep_time_minutes) ?? ""
            : "",
          totalTimeText: data.total_time_minutes !== null
            ? DurationSerializer.formatHuman(data.total_time_minutes) ?? ""
            : "",
          cookTimeText: data.cook_time_minutes !== null
            ? DurationSerializer.formatHuman(data.cook_time_minutes) ?? ""
            : "",
          performTimeText: data.perform_time_minutes !== null
            ? DurationSerializer.formatHuman(data.perform_time_minutes) ?? ""
            : "",
          author: data.author ?? "",
          datePublished: data.date_published ?? "",
          keywords: data.keywords ?? "",
          nutritionText: nutritionFromApi(data.nutrients ?? null),
          image_url: data.image_url ?? "",
          source_url: data.source_url,
          source_domain: data.source_domain,
        })
        if (data.steps) {
          setSteps(
            data.steps.map((s, idx) => ({
              key: `import-step-${idx}`,
              name: s.name ?? "",
              text: s.text,
            }))
          )
        }
        setImportedFrom(data.source_domain)
        setIsPartialImport(data.is_partial)
        setExistingRecipeId(data.existing_recipe_id ?? null)
        setError(null)
        if (data.suitable_for_diet_tag_ids && data.suitable_for_diet_tag_ids.length > 0) {
          setSelectedTagIds(data.suitable_for_diet_tag_ids)
        }
        const importedRows: IngredientRow[] = data.ingredients.map(
          (item, idx) => {
            const isLocked =
              item.confidence >= 1.0 && item.ingredient_id !== null
            const suggestedName = item.suggested_ingredient_name ?? null
            return {
              key: `import-${idx}`,
              ingredientId: isLocked ? (item.ingredient_id as number) : null,
              ingredientName: isLocked ? item.name : "",
              query: isLocked
                ? ""
                : suggestedName
                  ? suggestedName
                  : (item.raw || item.name),
              quantity: item.quantity !== null ? String(item.quantity) : "",
              unit: item.unit || "g",
              suggestedIngredientId:
                !isLocked && item.ingredient_id !== null
                  ? (item.ingredient_id as number)
                  : null,
              suggestedIngredientName: suggestedName,
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
    setSteps([])
    setMode("simple")
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
    (mode === "simple"
      ? form.stepsText.trim() !== ""
      : steps.some((s) => s.text.trim() !== "")) &&
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
        .filter(
          (r) => r.ingredientId !== null || r.suggestedIngredientName !== null
        )
        .map((r, idx) => ({
          ingredient_id: r.ingredientId !== null ? (r.ingredientId as number) : 0,
          quantity: parseQuantity(r.quantity),
          unit: r.unit,
          order_index: idx,
          suggested_ingredient_name: r.suggestedIngredientName,
          original_name: !r.ingredientId && r.suggestedIngredientName ? r.raw : null,
        }))
      const stepsPayload: RecipeStepPayload[] =
        mode === "extended"
          ? steps
              .filter((s) => s.text.trim() !== "")
              .map((s, position) => ({
                position,
                text: s.text,
                name: s.name.trim() || null,
              }))
          : form.stepsText
              .split("\n")
              .map((line) => line.trim())
              .filter((line) => line !== "")
              .map((text, position) => ({ position, text, name: null }))
      const extendedNull = mode === "simple"
      const cookMinutes = extendedNull
        ? null
        : DurationSerializer.parseHuman(form.cookTimeText)
      const performMinutes = extendedNull
        ? null
        : DurationSerializer.parseHuman(form.performTimeText)
      const authorOut = extendedNull ? null : toNull(form.author)
      const dateOut = extendedNull ? null : toNull(form.datePublished)
      const keywordsOut = extendedNull ? null : toNull(form.keywords)
      const nutritionOut = extendedNull
        ? null
        : parseNutrition(form.nutritionText)
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

      if (existingRecipeId !== null) {
        await putFullRecipe(existingRecipeId, {
          title: form.title.trim(),
          description: toNull(form.description),
          steps: stepsPayload,
          servings: form.servings,
          prep_time_minutes: DurationSerializer.parseHuman(form.prepTimeText),
          total_time_minutes: DurationSerializer.parseHuman(form.totalTimeText),
          cook_time_minutes: cookMinutes,
          perform_time_minutes: performMinutes,
          author: authorOut,
          date_published: dateOut,
          keywords: keywordsOut,
          nutrition: nutritionOut,
          image_url: toNull(form.image_url),
          source_url: toNull(form.source_url),
          source_domain: toNull(form.source_domain),
          ingredients,
          tag_ids: selectedTagIds,
        })
        navigate(`/recipes/${existingRecipeId}`)
        return
      }

      const created = await postRecipe({
        title: form.title.trim(),
        description: toNull(form.description),
        steps: stepsPayload,
        servings: form.servings,
        prep_time_minutes: DurationSerializer.parseHuman(form.prepTimeText),
        total_time_minutes: DurationSerializer.parseHuman(form.totalTimeText),
        cook_time_minutes: cookMinutes,
        perform_time_minutes: performMinutes,
        author: authorOut,
        date_published: dateOut,
        keywords: keywordsOut,
        nutrition: nutritionOut,
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

        <div className="flex items-center justify-between">
          <div></div>
          <LimitedExtendedToggle
            mode={mode}
            onChange={(newMode) => {
              if (newMode === "extended" && mode === "simple") {
                const splitSteps = form.stepsText
                  .split("\n")
                  .map((line) => line.trim())
                  .filter((line) => line !== "")
                  .map((text) => ({ ...defaultEditableStepValue(), text }))
                setSteps(splitSteps.length > 0 ? splitSteps : [defaultEditableStepValue()])
              }
              if (newMode === "simple" && mode === "extended") {
                update(
                  "stepsText",
                  steps.map((s) => s.text).join("\n")
                )
              }
              setMode(newMode)
            }}
          />
        </div>

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
          <label
            htmlFor="recipe-description"
            className="text-sm font-medium"
          >
            Beschreibung
          </label>
          <textarea
            id="recipe-description"
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-steps" className="text-sm font-medium">
            Zubereitung
          </label>
          {mode === "simple" ? (
            <textarea
              id="recipe-steps"
              value={form.stepsText}
              onChange={(e) => update("stepsText", e.target.value)}
              rows={6}
              required
              className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          ) : (
            <div className="space-y-2">
              {steps.map((step, idx) => (
                <EditableStepRow
                  key={step.key}
                  value={step}
                  onChange={(s) =>
                    setSteps((prev) =>
                      prev.map((r, i) => (i === idx ? s : r))
                    )
                  }
                  onRemove={() =>
                    setSteps((prev) => prev.filter((_, i) => i !== idx))
                  }
                  showNameInput={true}
                />
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  setSteps((prev) => [...prev, defaultEditableStepValue()])
                }
              >
                + Schritt hinzufügen
              </Button>
            </div>
          )}
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

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label
              htmlFor="recipe-prep-time"
              className="text-sm font-medium"
            >
              Vorbereitungszeit
            </label>
            <Input
              id="recipe-prep-time"
              type="text"
              value={form.prepTimeText}
              onChange={(e) => update("prepTimeText", e.target.value)}
              onBlur={() => {
                const parsed = DurationSerializer.parseHuman(
                  form.prepTimeText
                )
                if (parsed === null) return
                const formatted = DurationSerializer.formatHuman(parsed)
                update("prepTimeText", formatted ?? "")
              }}
              placeholder="z.B. 30 min"
            />
          </div>
          <div className="space-y-2">
            <label
              htmlFor="recipe-total-time"
              className="text-sm font-medium"
            >
              Gesamtzeit
            </label>
            <Input
              id="recipe-total-time"
              type="text"
              value={form.totalTimeText}
              onChange={(e) => update("totalTimeText", e.target.value)}
              onBlur={() => {
                const parsed = DurationSerializer.parseHuman(
                  form.totalTimeText
                )
                if (parsed === null) return
                const formatted = DurationSerializer.formatHuman(parsed)
                update("totalTimeText", formatted ?? "")
              }}
              placeholder="z.B. 1h 30m"
            />
          </div>
        </div>

        {mode === "extended" && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label
                  htmlFor="recipe-cook-time"
                  className="text-sm font-medium"
                >
                  Kochzeit
                </label>
                <Input
                  id="recipe-cook-time"
                  type="text"
                  value={form.cookTimeText}
                  onChange={(e) => update("cookTimeText", e.target.value)}
                  onBlur={() => {
                    const parsed = DurationSerializer.parseHuman(
                      form.cookTimeText
                    )
                    if (parsed === null) return
                    const formatted = DurationSerializer.formatHuman(parsed)
                    update("cookTimeText", formatted ?? "")
                  }}
                  placeholder="z.B. 45 min"
                />
              </div>
              <div className="space-y-2">
                <label
                  htmlFor="recipe-perform-time"
                  className="text-sm font-medium"
                >
                  Ruhezeit
                </label>
                <Input
                  id="recipe-perform-time"
                  type="text"
                  value={form.performTimeText}
                  onChange={(e) => update("performTimeText", e.target.value)}
                  onBlur={() => {
                    const parsed = DurationSerializer.parseHuman(
                      form.performTimeText
                    )
                    if (parsed === null) return
                    const formatted = DurationSerializer.formatHuman(parsed)
                    update("performTimeText", formatted ?? "")
                  }}
                  placeholder="z.B. 1h"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="recipe-author" className="text-sm font-medium">
                Autor
              </label>
              <Input
                id="recipe-author"
                type="text"
                value={form.author}
                onChange={(e) => update("author", e.target.value)}
                placeholder="z.B. Betty Bossi"
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="recipe-date-published"
                className="text-sm font-medium"
              >
                Veröffentlicht am
              </label>
              <Input
                id="recipe-date-published"
                type="date"
                value={form.datePublished}
                onChange={(e) => update("datePublished", e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="recipe-keywords"
                className="text-sm font-medium"
              >
                Schlagwörter
              </label>
              <Input
                id="recipe-keywords"
                type="text"
                value={form.keywords}
                onChange={(e) => update("keywords", e.target.value)}
                placeholder="kommagetrennt, z.B. schnell, gesund"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium">Bewertung</label>
                <span className="text-xs text-muted-foreground">
                  Keine eigene Bewertung möglich
                </span>
              </div>
            </div>

            <NutritionEditor
              nutrition={form.nutritionText}
              onChange={(n) => update("nutritionText", n)}
            />
          </>
        )}

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
              <EditableIngredientRow
                key={row.key}
                value={row}
                onChange={(r) => updateRow(idx, r)}
                onRemove={() => removeRow(idx)}
              />
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
