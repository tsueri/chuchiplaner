import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { EditableIngredientRow } from "@/components/EditableIngredientRow"
import {
  defaultEditableIngredientValue,
  type EditableIngredientValue,
} from "@/components/EditableIngredientRow.types"
import { cn } from "@/lib/utils"
import { useAuth } from "@/contexts/useAuth"
import { PageHeader } from "@/components/PageHeader"

interface RecipeDetail {
  id: number
  title: string
  description: string | null
  image_url: string | null
  source_url: string | null
  source_domain: string | null
  servings: number
  prep_time_minutes: number | null
  cook_time_minutes: number | null
  total_time_minutes: number | null
  perform_time_minutes: number | null
  nutrition: Record<string, unknown> | null
  aggregate_rating: Record<string, unknown> | null
  keywords: string | null
  author: string | null
  date_published: string | null
  household_id: number
  ingredients: {
    id: number
    ingredient_id: number
    ingredient_name: string
    quantity: number
    unit: string
    order_index: number
  }[]
  steps: {
    id: number
    position: number
    text: string
    name: string | null
  }[]
  tags: { id: number; name: string; group: string; household_id: number | null }[]
  is_favorited: boolean
  created_at: string | null
}

interface RecipeNote {
  id: number
  recipe_id: number
  user_id: number
  text: string
  visibility: string
  username: string | null
  created_at: string | null
  updated_at: string | null
}

interface TagItem {
  id: number
  name: string
  group: string
  household_id: number | null
}

interface EditState {
  title: string
  stepsText: string
  servings: number
  image_url: string
  source_url: string
  source_domain: string
  rows: EditableIngredientValue[]
  selectedTagIds: number[]
}

function buildEditState(recipe: RecipeDetail): EditState {
  const stepsText = recipe.steps
    .sort((a, b) => a.position - b.position)
    .map((s) => s.text)
    .join("\n")
  return {
    title: recipe.title,
    stepsText,
    servings: recipe.servings,
    image_url: recipe.image_url ?? "",
    source_url: recipe.source_url ?? "",
    source_domain: recipe.source_domain ?? "",
    rows: recipe.ingredients.map((ing, idx) => ({
      key: `existing-${ing.id}-${idx}`,
      ingredientId: ing.ingredient_id,
      ingredientName: ing.ingredient_name,
      query: "",
      quantity: String(ing.quantity),
      unit: ing.unit,
      suggestedIngredientId: null,
      confidence: 1.0,
      raw: "",
    })),
    selectedTagIds: recipe.tags.map((t) => t.id),
  }
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

function parseQuantity(value: string): number {
  const n = parseFloat(value)
  return Number.isFinite(n) ? n : 0
}

function emptyToNull(value: string): string | null {
  return value.trim() === "" ? null : value
}

export default function RecipeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()

  const [recipe, setRecipe] = useState<RecipeDetail | null>(null)
  const [notes, setNotes] = useState<RecipeNote[]>([])
  const [tags, setTags] = useState<TagItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)

  const [newNote, setNewNote] = useState("")
  const [noteVisibility, setNoteVisibility] = useState("private")
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null)
  const [editNoteText, setEditNoteText] = useState("")
  const [editNoteVisibility, setEditNoteVisibility] = useState("private")

  const [editState, setEditState] = useState<EditState | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const doFetchRecipe = useCallback(async () => {
    if (!id) throw new Error("No recipe id")
    return (await api(`/recipes/${id}`)) as RecipeDetail
  }, [id])

  const doFetchNotes = useCallback(async () => {
    if (!id) throw new Error("No recipe id")
    return (await api(`/recipes/${id}/notes`)) as RecipeNote[]
  }, [id])

  const doFetchTags = useCallback(async () => {
    return (await api("/tags")) as TagItem[]
  }, [])

  const refreshAll = useCallback(() => {
    let cancelled = false
    Promise.all([doFetchRecipe(), doFetchNotes(), doFetchTags()])
      .then(([r, n, t]) => {
        if (!cancelled) {
          setRecipe(r)
          setNotes(n)
          setTags(t)
          setError(null)
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "Recipe not found")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [doFetchRecipe, doFetchNotes, doFetchTags])

  useEffect(() => {
    const cancel = refreshAll()
    return cancel
  }, [refreshAll])

  const toggleFavorite = async () => {
    if (!id) return
    await api(`/recipes/${id}/favorite`, { method: "POST" })
    refreshAll()
  }

  const addNote = async () => {
    if (!id || !newNote.trim()) return
    await api(`/recipes/${id}/notes`, {
      method: "POST",
      body: JSON.stringify({ text: newNote.trim(), visibility: noteVisibility }),
    })
    setNewNote("")
    refreshAll()
  }

  const updateNote = async (noteId: number) => {
    if (!id || !editNoteText.trim()) return
    await api(`/recipes/${id}/notes/${noteId}`, {
      method: "PUT",
      body: JSON.stringify({
        text: editNoteText.trim(),
        visibility: editNoteVisibility,
      }),
    })
    setEditingNoteId(null)
    refreshAll()
  }

  const deleteNote = async (noteId: number) => {
    if (!id) return
    await api(`/recipes/${id}/notes/${noteId}`, { method: "DELETE" })
    refreshAll()
  }

  const updateTags = async (tagIds: number[]) => {
    if (!id) return
    await api(`/recipes/${id}`, {
      method: "PUT",
      body: JSON.stringify({ tag_ids: tagIds }),
    })
    refreshAll()
  }

  const toggleTag = (tagId: number) => {
    if (!recipe) return
    const currentIds = recipe.tags.map((t) => t.id)
    if (currentIds.includes(tagId)) {
      updateTags(currentIds.filter((t) => t !== tagId))
    } else {
      updateTags([...currentIds, tagId])
    }
  }

  const deleteRecipe = async () => {
    if (!id) return
    if (!confirm("Rezept wirklich löschen?")) return
    await api(`/recipes/${id}`, { method: "DELETE" })
    navigate("/recipes")
  }

  const enterEditMode = () => {
    if (!recipe) return
    setEditState(buildEditState(recipe))
    setEditError(null)
    setIsEditing(true)
  }

  const cancelEdit = () => {
    setIsEditing(false)
    setEditState(null)
    setEditError(null)
  }

  const updateEditField = <K extends keyof EditState>(
    key: K,
    value: EditState[K]
  ) => {
    setEditState((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  const addRow = () => {
    setEditState((prev) =>
      prev ? { ...prev, rows: [...prev.rows, defaultEditableIngredientValue()] } : prev
    )
  }

  const updateRow = (idx: number, row: EditableIngredientValue) => {
    setEditState((prev) =>
      prev
        ? {
            ...prev,
            rows: prev.rows.map((r, i) => (i === idx ? row : r)),
          }
        : prev
    )
  }

  const removeRow = (idx: number) => {
    setEditState((prev) =>
      prev ? { ...prev, rows: prev.rows.filter((_, i) => i !== idx) } : prev
    )
  }

  const toggleEditTag = (tagId: number) => {
    setEditState((prev) => {
      if (!prev) return prev
      const isActive = prev.selectedTagIds.includes(tagId)
      return {
        ...prev,
        selectedTagIds: isActive
          ? prev.selectedTagIds.filter((id) => id !== tagId)
          : [...prev.selectedTagIds, tagId],
      }
    })
  }

  const canSave = useMemo(() => {
    if (!editState) return false
    if (saving) return false
    if (editState.title.trim() === "") return false
    if (editState.stepsText.trim() === "") return false
    return true
  }, [editState, saving])

  const saveEdit = async () => {
    if (!editState || !id) return
    setSaving(true)
    setEditError(null)
    const ingredients = editState.rows
      .filter((r) => r.ingredientId !== null)
      .map((r, idx) => ({
        ingredient_id: r.ingredientId as number,
        quantity: parseQuantity(r.quantity),
        unit: r.unit,
        order_index: idx,
      }))
    const steps = editState.stepsText
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line !== "")
      .map((text, position) => ({ position, text, name: null }))
    try {
      const updated = (await api(`/recipes/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          title: editState.title.trim(),
          steps,
          servings: editState.servings,
          image_url: emptyToNull(editState.image_url),
          source_url: emptyToNull(editState.source_url),
          source_domain: emptyToNull(editState.source_domain),
          tag_ids: editState.selectedTagIds,
          ingredients,
        }),
      })) as RecipeDetail
      setRecipe(updated)
      setIsEditing(false)
      setEditState(null)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Speichern fehlgeschlagen")
    } finally {
      setSaving(false)
    }
  }

  if (loading)
    return <div className="p-4">Lade Rezept...</div>
  if (error || !recipe)
    return <div className="p-4 text-red-600">{error || "Rezept nicht gefunden"}</div>

  if (isEditing && editState) {
    return (
      <div>
        <PageHeader title="Rezept bearbeiten" />
        <button
          onClick={cancelEdit}
          className="mb-4 text-sm text-primary hover:underline"
        >
          &larr; Abbrechen
        </button>

        {editError && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive"
          >
            {editError}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (canSave) saveEdit()
          }}
          className="mx-auto max-w-2xl space-y-4 rounded-lg border bg-card p-6"
        >
          <div className="space-y-2">
            <label htmlFor="edit-recipe-title" className="text-sm font-medium">
              Titel
            </label>
            <Input
              id="edit-recipe-title"
              type="text"
              value={editState.title}
              onChange={(e) => updateEditField("title", e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="edit-recipe-steps"
              className="text-sm font-medium"
            >
              Zubereitung
            </label>
            <textarea
              id="edit-recipe-steps"
              value={editState.stepsText}
              onChange={(e) => updateEditField("stepsText", e.target.value)}
              rows={6}
              required
              className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="edit-recipe-servings" className="text-sm font-medium">
              Portionen
            </label>
            <Input
              id="edit-recipe-servings"
              type="number"
              min={1}
              value={editState.servings}
              onChange={(e) =>
                updateEditField(
                  "servings",
                  Math.max(1, Number(e.target.value) || 1)
                )
              }
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="edit-recipe-image-url" className="text-sm font-medium">
              Bild-URL
            </label>
            <Input
              id="edit-recipe-image-url"
              type="url"
              value={editState.image_url}
              onChange={(e) => updateEditField("image_url", e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="edit-recipe-source-url" className="text-sm font-medium">
              Quelle
            </label>
            <Input
              id="edit-recipe-source-url"
              type="url"
              value={editState.source_url}
              onChange={(e) => updateEditField("source_url", e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="edit-recipe-source-domain"
              className="text-sm font-medium"
            >
              Quell-Domain
            </label>
            <Input
              id="edit-recipe-source-domain"
              type="text"
              value={editState.source_domain}
              onChange={(e) => updateEditField("source_domain", e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <h2 className="text-sm font-medium">Tags</h2>
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => {
                const isActive = editState.selectedTagIds.includes(tag.id)
                return (
                  <button
                    key={tag.id}
                    type="button"
                    aria-pressed={isActive}
                    onClick={() => toggleEditTag(tag.id)}
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
              {editState.rows.map((row, idx) => (
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
            <Button
              type="button"
              onClick={cancelEdit}
              variant="outline"
              size="sm"
            >
              Abbrechen
            </Button>
            <Button type="submit" disabled={!canSave}>
              {saving ? "Wird gespeichert..." : "Speichern"}
            </Button>
          </div>
        </form>
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="Rezept" />
      <button
        onClick={() => navigate("/recipes")}
        className="mb-4 text-sm text-primary hover:underline"
      >
        &larr; Zurück zur Liste
      </button>

      <div className="mb-4 flex justify-end">
        <Button onClick={enterEditMode} variant="outline" size="sm">
          Bearbeiten
        </Button>
      </div>

      {recipe.image_url && (
        <img
          src={recipe.image_url}
          alt={recipe.title}
          className="mb-4 w-full max-h-64 rounded-lg object-cover"
        />
      )}

      <div className="flex items-start justify-between">
        <h1 className="text-2xl font-bold">{recipe.title}</h1>
        <button
          onClick={toggleFavorite}
          className={cn(
            "text-2xl",
            recipe.is_favorited ? "text-yellow-500" : "text-gray-300"
          )}
          title={recipe.is_favorited ? "Favorit entfernen" : "Favorit"}
        >
          ★
        </button>
      </div>

      {recipe.source_url && (
        <a
          href={recipe.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-primary hover:underline"
        >
          {recipe.source_domain || "Original-Rezept"}
        </a>
      )}

      <p className="mt-2 text-sm text-muted-foreground">
        {recipe.servings} Portionen
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="text-sm font-medium text-muted-foreground">Tags:</span>
        {tags.map((tag) => {
          const isActive = recipe.tags.some((t) => t.id === tag.id)
          return (
            <span
              key={tag.id}
              onClick={() => toggleTag(tag.id)}
              className={cn(
                "cursor-pointer rounded-full px-3 py-1 text-sm transition",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted-foreground/20"
              )}
            >
              {tag.name}
            </span>
          )
        })}
      </div>

      {recipe.ingredients.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold">Zutaten</h2>
          <ul className="mt-2 list-inside list-disc">
            {recipe.ingredients.map((ing) => (
              <li key={ing.id}>
                {ing.quantity} {ing.unit} {ing.ingredient_name}
              </li>
            ))}
          </ul>
        </div>
      )}

      {recipe.steps.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold">Zubereitung</h2>
          <ol className="mt-2 list-inside list-decimal space-y-3">
            {recipe.steps
              .sort((a, b) => a.position - b.position)
              .map((step) => (
                <li key={step.id} className="text-sm leading-relaxed">
                  {step.name && (
                    <h3 className="mb-1 text-base font-medium">{step.name}</h3>
                  )}
                  <p className="whitespace-pre-wrap">{step.text}</p>
                </li>
              ))}
          </ol>
        </div>
      )}

      <div className="mt-8">
        <h2 className="text-lg font-semibold">Notizen</h2>

        <div className="mt-3 flex flex-col gap-2">
          <textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Neue Notiz..."
            rows={2}
            className="rounded border px-3 py-2 text-sm"
          />
          <div className="flex items-center gap-2">
            <select
              value={noteVisibility}
              onChange={(e) => setNoteVisibility(e.target.value)}
              className="rounded border px-2 py-1 text-sm"
            >
              <option value="private">Privat</option>
              <option value="household">Haushalt</option>
            </select>
            <Button onClick={addNote} size="sm" disabled={!newNote.trim()}>
              Speichern
            </Button>
          </div>
        </div>

        {notes.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">Keine Notizen.</p>
        ) : (
          <div className="mt-4 space-y-3">
            {notes.map((note) => (
              <div key={note.id} className="rounded border bg-card p-3">
                {editingNoteId === note.id ? (
                  <div className="flex flex-col gap-2">
                    <textarea
                      value={editNoteText}
                      onChange={(e) => setEditNoteText(e.target.value)}
                      rows={2}
                      className="rounded border px-2 py-1 text-sm"
                    />
                    <div className="flex items-center gap-2">
                      <select
                        value={editNoteVisibility}
                        onChange={(e) => setEditNoteVisibility(e.target.value)}
                        className="rounded border px-2 py-1 text-sm"
                      >
                        <option value="private">Privat</option>
                        <option value="household">Haushalt</option>
                      </select>
                      <Button onClick={() => updateNote(note.id)} size="sm">
                        Aktualisieren
                      </Button>
                      <Button
                        onClick={() => setEditingNoteId(null)}
                        variant="outline"
                        size="sm"
                      >
                        Abbrechen
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="whitespace-pre-wrap text-sm">{note.text}</p>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                      {note.username && <span>{note.username}</span>}
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5",
                          note.visibility === "household"
                            ? "bg-blue-100 text-blue-800"
                            : "bg-gray-100 text-gray-600"
                        )}
                      >
                        {note.visibility === "household" ? "Haushalt" : "Privat"}
                      </span>
                      {note.created_at && (
                        <span>
                          {new Date(note.created_at).toLocaleDateString("de-DE")}
                        </span>
                      )}
                      {note.user_id === user?.id && (
                        <div className="flex gap-1">
                          <button
                            onClick={() => {
                              setEditingNoteId(note.id)
                              setEditNoteText(note.text)
                              setEditNoteVisibility(note.visibility)
                            }}
                            className="text-primary hover:underline"
                          >
                            Bearbeiten
                          </button>
                          <button
                            onClick={() => deleteNote(note.id)}
                            className="text-red-600 hover:underline"
                          >
                            Löschen
                          </button>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {user?.role === "admin" && (
        <div className="mt-8 border-t pt-4">
          <Button onClick={deleteRecipe} variant="destructive" size="sm">
            Rezept löschen
          </Button>
        </div>
      )}
    </div>
  )
}
