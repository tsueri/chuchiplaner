import { useCallback, useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useAuth } from "@/contexts/useAuth"
import { PageHeader } from "@/components/PageHeader"

interface RecipeDetail {
  id: number
  title: string
  instructions: string
  image_url: string | null
  source_url: string | null
  source_domain: string | null
  servings: number
  household_id: number
  ingredients: {
    id: number
    ingredient_id: number
    quantity: number
    unit: string
    order_index: number
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

export default function RecipeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()

  const [recipe, setRecipe] = useState<RecipeDetail | null>(null)
  const [notes, setNotes] = useState<RecipeNote[]>([])
  const [tags, setTags] = useState<TagItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [newNote, setNewNote] = useState("")
  const [noteVisibility, setNoteVisibility] = useState("private")
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null)
  const [editNoteText, setEditNoteText] = useState("")
  const [editNoteVisibility, setEditNoteVisibility] = useState("private")

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

  if (loading)
    return <div className="p-4">Lade Rezept...</div>
  if (error || !recipe)
    return <div className="p-4 text-red-600">{error || "Rezept nicht gefunden"}</div>

  return (
    <div>
      <PageHeader title="Rezept" />
      <button
        onClick={() => navigate("/recipes")}
        className="mb-4 text-sm text-primary hover:underline"
      >
        &larr; Zurück zur Liste
      </button>

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
                {ing.quantity} {ing.unit}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6">
        <h2 className="text-lg font-semibold">Zubereitung</h2>
        <div className="mt-2 whitespace-pre-wrap rounded bg-muted/30 p-3 text-sm leading-relaxed">
          {recipe.instructions}
        </div>
      </div>

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
