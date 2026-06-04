import { useCallback, useEffect, useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { PageHeader } from "@/components/PageHeader"

interface RecipeIngredient {
  id: number
  ingredient_id: number
  ingredient_name: string
  quantity: number
  unit: string
  order_index: number
}

interface RecipeStep {
  id: number
  position: number
  text: string
  name: string | null
}

interface RecipeItem {
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
  tags: TagItem[]
  is_favorited: boolean
  created_at: string | null
  ingredients: RecipeIngredient[]
  steps: RecipeStep[]
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

function buildSnippet(recipe: RecipeItem): string | null {
  if (recipe.description && recipe.description.trim() !== "") {
    return recipe.description
  }
  const stepsText = [...recipe.steps]
    .sort((a, b) => a.position - b.position)
    .map((s) => s.text)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim()
  if (stepsText === "") return null
  if (stepsText.length <= 140) return stepsText
  return stepsText.slice(0, 140).trimEnd() + "…"
}

export default function RecipeListPage() {
  const navigate = useNavigate()
  const [recipes, setRecipes] = useState<RecipeItem[]>([])
  const [tags, setTags] = useState<TagItem[]>([])
  const [search, setSearch] = useState("")
  const [tagFilter, setTagFilter] = useState<number | null>(null)
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [importUrl, setImportUrl] = useState("")
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const handleImportSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = importUrl.trim()
    if (trimmed === "") return
    navigate(`/recipes/new?url=${encodeURIComponent(trimmed)}`)
  }

  const doFetchRecipes = useCallback(
    async (q: string, tag: number | null, favs: boolean) => {
      const params = new URLSearchParams()
      if (q) params.set("search", q)
      if (tag) params.set("tag_id", String(tag))
      if (favs) params.set("favorites_only", "true")
      params.set("limit", "100")
      return (await api(`/recipes?${params.toString()}`)) as RecipeItem[]
    },
    []
  )

  const refreshRecipes = useCallback(
    (q: string, tag: number | null, favs: boolean) => {
      let cancelled = false
      doFetchRecipes(q, tag, favs)
        .then((data) => {
          if (!cancelled) {
            setRecipes(data)
            setError(null)
          }
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message || "Failed to load recipes")
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
      return () => {
        cancelled = true
      }
    },
    [doFetchRecipes]
  )

  useEffect(() => {
    const cancel = refreshRecipes(search, tagFilter, favoritesOnly)
    api("/tags").then(setTags).catch(() => {})
    return cancel
  }, [search, tagFilter, favoritesOnly, refreshRecipes])

  const toggleFavorite = async (id: number) => {
    await api(`/recipes/${id}/favorite`, { method: "POST" })
    refreshRecipes(search, tagFilter, favoritesOnly)
  }

  const toggleExpanded = (id: number) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  return (
    <div>
      <PageHeader
        title="Rezepte"
        actions={
          <>
            <form
              onSubmit={handleImportSubmit}
              className="flex items-center gap-2"
            >
              <Input
                type="url"
                value={importUrl}
                onChange={(e) => setImportUrl(e.target.value)}
                placeholder="Aus URL importieren…"
                aria-label="Aus URL importieren"
                className="h-8 w-56"
              />
              <Button
                type="submit"
                variant="outline"
                size="sm"
                disabled={importUrl.trim() === ""}
              >
                Importieren
              </Button>
            </form>
            <Link
              to="/recipes/new"
              className={buttonVariants({ variant: "default" })}
            >
              Neues Rezept
            </Link>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="Rezept suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded border px-3 py-2"
        />
        <Button
          onClick={() => setFavoritesOnly(!favoritesOnly)}
          variant={favoritesOnly ? "default" : "outline"}
        >
          Favoriten
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <span
          onClick={() => setTagFilter(null)}
          className={cn(
            "cursor-pointer rounded-full px-3 py-1 text-sm",
            !tagFilter ? "bg-primary text-primary-foreground" : "bg-muted"
          )}
        >
          Alle
        </span>
        {tags.map((tag) => (
          <span
            key={tag.id}
            onClick={() => setTagFilter(tag.id === tagFilter ? null : tag.id)}
            className={cn(
              "cursor-pointer rounded-full px-3 py-1 text-sm",
              tag.id === tagFilter
                ? "bg-primary text-primary-foreground"
                : tag.group === "season"
                  ? "bg-green-100 text-green-800"
                  : "bg-muted"
            )}
          >
            {tag.name}
          </span>
        ))}
      </div>

      {error && <p className="mb-4 text-red-600">{error}</p>}

      {loading ? (
        <p>Lade Rezepte...</p>
      ) : recipes.length === 0 ? (
        <p className="text-muted-foreground">Keine Rezepte gefunden.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {recipes.map((r) => {
            const isExpanded = expandedId === r.id
            const sortedIngredients = [...r.ingredients].sort(
              (a, b) => a.order_index - b.order_index
            )
            const snippet = buildSnippet(r)
            return (
              <div
                key={r.id}
                className="rounded-lg border bg-card p-4 shadow-sm transition hover:shadow-md"
              >
                <div className="flex items-start justify-between">
                  <Link
                    to={`/recipes/${r.id}`}
                    className="text-lg font-semibold hover:underline"
                  >
                    {r.title}
                  </Link>
                  <button
                    onClick={() => toggleFavorite(r.id)}
                    className={cn(
                      "text-xl",
                      r.is_favorited ? "text-yellow-500" : "text-gray-300"
                    )}
                    title={r.is_favorited ? "Favorit entfernen" : "Favorit"}
                  >
                    ★
                  </button>
                </div>
                {r.image_url && (
                  <img
                    src={r.image_url}
                    alt={r.title}
                    className="mt-2 h-32 w-full rounded object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none"
                    }}
                  />
                )}
                {snippet && (
                  <p
                    className="mt-2 text-sm text-muted-foreground"
                    data-testid="recipe-snippet"
                  >
                    {snippet}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap gap-1">
                  {r.tags.map((tag) => (
                    <span
                      key={tag.id}
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs",
                        tag.group === "season"
                          ? "bg-green-100 text-green-800"
                          : "bg-blue-100 text-blue-800"
                      )}
                    >
                      {tag.name}
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {r.servings} Portionen
                  {r.source_domain ? ` \u00b7 ${r.source_domain}` : ""}
                </p>
                {sortedIngredients.length > 0 && (
                  <div className="mt-3">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-expanded={isExpanded}
                      onClick={() => toggleExpanded(r.id)}
                    >
                      {isExpanded ? "Zutaten verbergen" : "Zutaten anzeigen"}
                    </Button>
                    {isExpanded && (
                      <ul className="mt-2 list-inside list-disc text-sm">
                        {sortedIngredients.map((ing) => (
                          <li key={ing.id}>
                            {ing.quantity} {ing.unit} {ing.ingredient_name}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
