import { useCallback, useEffect, useState } from "react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/PageHeader"

interface RecipeData {
  id: number
  title: string
  description: string | null
  image_url: string | null
  servings: number
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
}

interface InventoryItem {
  id: number
  ingredient_id: number
  ingredient_name: string
  quantity: number
  unit: string
  category: string
  expiry_date: string | null
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

function getInventoryForIngredient(
  inventory: InventoryItem[],
  ingredientId: number,
): { quantity: number; unit: string } | null {
  for (const item of inventory) {
    if (item.ingredient_id === ingredientId) return item
  }
  return null
}

export default function CookModePage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const recipeId = Number(id)
  const initialPortions = Number(searchParams.get("portions")) || 4

  const [recipe, setRecipe] = useState<RecipeData | null>(null)
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [portions, setPortions] = useState(initialPortions)
  const [checkedIngredients, setCheckedIngredients] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [cooking, setCooking] = useState(false)
  const [showLeftovers, setShowLeftovers] = useState(false)
  const [leftoverPortions, setLeftoverPortions] = useState(2)
  const [error, setError] = useState("")

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api(`/recipes/${recipeId}`),
      api("/inventory?category=raw"),
    ])
      .then(([recipeData, invData]) => {
        if (!cancelled) {
          setRecipe(recipeData as RecipeData)
          setInventory(invData as InventoryItem[])
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [recipeId])

  const toggleIngredient = useCallback((ingredientId: number) => {
    setCheckedIngredients((prev) => {
      const next = new Set(prev)
      if (next.has(ingredientId)) {
        next.delete(ingredientId)
      } else {
        next.add(ingredientId)
      }
      return next
    })
  }, [])

  const handleCook = async () => {
    if (!recipe) return
    setCooking(true)
    setError("")
    try {
      const slotId = searchParams.get("slotId")
      const year = searchParams.get("year")
      const isoWeek = searchParams.get("isoWeek")

      await api(`/recipes/${recipeId}/cook`, {
        method: "POST",
        body: JSON.stringify({
          portions,
          ...(slotId ? { slot_id: Number(slotId) } : {}),
          ...(year ? { year: Number(year) } : {}),
          ...(isoWeek ? { iso_week: Number(isoWeek) } : {}),
        }),
      })
      setShowLeftovers(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cook")
    } finally {
      setCooking(false)
    }
  }

  const handleSaveLeftovers = async () => {
    if (!recipe) return
    setCooking(true)
    try {
      const slotId = searchParams.get("slotId")
      const year = searchParams.get("year")
      const isoWeek = searchParams.get("isoWeek")

      await api(`/recipes/${recipeId}/leftovers`, {
        method: "POST",
        body: JSON.stringify({
          portions_count: leftoverPortions,
          ...(slotId ? { slot_id: Number(slotId) } : {}),
          ...(year ? { year: Number(year) } : {}),
          ...(isoWeek ? { iso_week: Number(isoWeek) } : {}),
        }),
      })
      setShowLeftovers(false)
      navigate(-1)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save leftovers")
      setCooking(false)
    }
  }

  const handleSkipLeftovers = () => {
    setShowLeftovers(false)
    navigate(-1)
  }

  const scale = recipe ? portions / recipe.servings : 1

  if (loading) {
    return <p className="p-4 text-muted-foreground">Laden...</p>
  }

  if (error && !recipe) {
    return <p className="p-4 text-destructive">{error}</p>
  }

  if (!recipe) {
    return <p className="p-4 text-muted-foreground">Rezept nicht gefunden.</p>
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader title={recipe.title} />

      <main className="flex-1 p-6 md:p-8 overflow-y-auto">
        {/* Section 1: Image, title, description, portions stepper */}
        <div className="space-y-4">
          {recipe.image_url && (
            <img
              src={recipe.image_url}
              alt={recipe.title}
              className="w-full max-h-64 object-cover rounded-lg"
            />
          )}
          <h1 className="text-2xl font-bold">{recipe.title}</h1>
          {recipe.description && (
            <p className="text-muted-foreground">{recipe.description}</p>
          )}
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPortions(Math.max(1, portions - 1))}
              disabled={portions <= 1}
            >
              -
            </Button>
            <span className="font-medium">{portions} Portionen</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPortions(portions + 1)}
            >
              +
            </Button>
          </div>
        </div>

        {/* Section 2: Mise en place — ingredient checklist */}
        <div className="mt-8">
          <h2 className="text-lg font-semibold">Mise en Place</h2>
          <ul className="mt-3 space-y-2">
            {recipe.ingredients.map((ing) => {
              const scaledQuantity = ing.quantity * scale
              const inv = getInventoryForIngredient(inventory, ing.ingredient_id)
              return (
                <li key={ing.id} className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={checkedIngredients.has(ing.id)}
                    onChange={() => toggleIngredient(ing.id)}
                    className="h-4 w-4"
                  />
                  <span
                    className={checkedIngredients.has(ing.id) ? "line-through text-muted-foreground" : ""}
                  >
                    {Number.isInteger(scaledQuantity) ? scaledQuantity : scaledQuantity.toFixed(1)} {ing.unit} {ing.ingredient_name}
                  </span>
                  {inv && (
                    <span className="text-xs text-muted-foreground">
                      (im Vorrat: {Number.isInteger(inv.quantity) ? inv.quantity : inv.quantity.toFixed(1)} {inv.unit})
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>

        {/* Section 3: Steps */}
        <div className="mt-8">
          <h2 className="text-lg font-semibold">Zubereitung</h2>
          <ol className="mt-3 list-inside list-decimal space-y-3">
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

        {error && (
          <p className="mt-4 text-sm text-destructive">{error}</p>
        )}

        {/* Gekocht button */}
        <div className="mt-8 pb-8">
          <Button
            onClick={handleCook}
            disabled={cooking}
            size="lg"
            className="w-full"
          >
            {cooking ? "Koche..." : "Gekocht"}
          </Button>
        </div>
      </main>

      {/* Leftovers modal */}
      {showLeftovers && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-card rounded-lg shadow-lg p-6 w-full max-w-sm mx-4">
            <h2 className="text-lg font-semibold">Wie viele Portionen sind übrig?</h2>
            <div className="mt-4">
              <input
                type="number"
                min={1}
                value={leftoverPortions}
                onChange={(e) => setLeftoverPortions(Number(e.target.value))}
                className="w-full rounded border px-3 py-2 text-sm"
              />
            </div>
            {error && (
              <p className="mt-2 text-sm text-destructive">{error}</p>
            )}
            <div className="mt-4 flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={handleSkipLeftovers}>
                Überspringen
              </Button>
              <Button size="sm" onClick={handleSaveLeftovers} disabled={cooking}>
                Speichern
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
