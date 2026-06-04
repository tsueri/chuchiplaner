import { useCallback, useEffect, useState } from "react"
import type { FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { PageHeader } from "@/components/PageHeader"

interface InventoryItem {
  id: number
  household_id: number
  ingredient_id: number
  ingredient_name: string
  quantity: number
  unit: string
  expiry_date: string | null
  category: string
  created_at: string | null
  updated_at: string | null
}

interface Ingredient {
  id: number
  name: string
}

type SortMode = "expiry" | "name" | "category"
type CategoryFilter = "all" | "raw" | "cooked" | "frozen"

const UNITS = ["g", "kg", "ml", "l", "EL", "TL", "St\u00fcck", "Bund", "Prise"]

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

function getExpiryClass(expiryDate: string | null): string {
  if (!expiryDate) return ""
  const now = new Date()
  const expiry = new Date(expiryDate)
  const diffMs = expiry.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  if (diffDays < 0) return "text-red-600 font-semibold"
  if (diffDays <= 3) return "text-orange-500 font-semibold"
  return ""
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014"
  return new Date(dateStr).toLocaleDateString("de-DE")
}

function categoryLabel(cat: string): string {
  const labels: Record<string, string> = {
    raw: "Roh",
    cooked: "Gekocht",
    frozen: "Tiefgefroren",
  }
  return labels[cat] || cat
}

function categoryBadgeClass(cat: string): string {
  const classes: Record<string, string> = {
    raw: "bg-green-100 text-green-800",
    cooked: "bg-blue-100 text-blue-800",
    frozen: "bg-purple-100 text-purple-800",
  }
  return classes[cat] || "bg-gray-100 text-gray-800"
}

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([])
  const [ingredients, setIngredients] = useState<Ingredient[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [sortMode, setSortMode] = useState<SortMode>("expiry")
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all")
  const [search, setSearch] = useState("")

  // Add form state
  const [showAddForm, setShowAddForm] = useState(false)
  const [addIngredientSearch, setAddIngredientSearch] = useState("")
  const [addIngredientId, setAddIngredientId] = useState<number | null>(null)
  const [addQuantity, setAddQuantity] = useState("")
  const [addUnit, setAddUnit] = useState("g")
  const [addExpiryDate, setAddExpiryDate] = useState("")
  const [addCategory, setAddCategory] = useState<string>("raw")
  const [showIngredientDropdown, setShowIngredientDropdown] = useState(false)
  const [addSubmitting, setAddSubmitting] = useState(false)
  const [addError, setAddError] = useState("")

  // Edit state
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null)
  const [editQuantity, setEditQuantity] = useState("")
  const [editUnit, setEditUnit] = useState("")
  const [editExpiryDate, setEditExpiryDate] = useState("")
  const [editCategory, setEditCategory] = useState("")
  const [editSubmitting, setEditSubmitting] = useState(false)
  const [editError, setEditError] = useState("")

  const doFetchItems = useCallback(async (cat: CategoryFilter) => {
    const params = new URLSearchParams()
    if (cat !== "all") params.set("category", cat)
    const data: InventoryItem[] = await api(
      `/inventory?${params.toString()}`
    )
    return data
  }, [])

  const refreshItems = useCallback(
    (cat: CategoryFilter) => {
      let cancelled = false
      doFetchItems(cat)
        .then((data) => {
          if (!cancelled) {
            setItems(data)
            setError("")
          }
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message || "Failed to load inventory")
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
      return () => {
        cancelled = true
      }
    },
    [doFetchItems]
  )

  useEffect(() => {
    const cancel = refreshItems(categoryFilter)
    api("/ingredients")
      .then((data: Ingredient[]) => setIngredients(data))
      .catch(() => {})
    return cancel
  }, [categoryFilter, refreshItems])

  const sortedItems = [...items].sort((a, b) => {
    switch (sortMode) {
      case "name":
        return a.ingredient_name.localeCompare(b.ingredient_name)
      case "category":
        return a.category.localeCompare(b.category)
      case "expiry":
      default: {
        if (!a.expiry_date && !b.expiry_date) return 0
        if (!a.expiry_date) return 1
        if (!b.expiry_date) return -1
        return a.expiry_date.localeCompare(b.expiry_date)
      }
    }
  })

  const filteredItems = search
    ? sortedItems.filter((item) =>
        item.ingredient_name.toLowerCase().includes(search.toLowerCase())
      )
    : sortedItems

  const filteredIngredients = ingredients.filter((ing) =>
    ing.name.toLowerCase().includes(addIngredientSearch.toLowerCase())
  )

  const handleAddSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setAddError("")
    if (!addIngredientId) {
      setAddError("Bitte eine Zutat ausw\u00e4hlen")
      return
    }
    setAddSubmitting(true)
    try {
      await api("/inventory", {
        method: "POST",
        body: JSON.stringify({
          ingredient_id: addIngredientId,
          quantity: parseFloat(addQuantity),
          unit: addUnit,
          expiry_date: addExpiryDate || null,
          category: addCategory,
        }),
      })
      setShowAddForm(false)
      setAddIngredientSearch("")
      setAddIngredientId(null)
      setAddQuantity("")
      setAddUnit("g")
      setAddExpiryDate("")
      setAddCategory("raw")
      refreshItems(categoryFilter)
    } catch (err) {
      setAddError(
        err instanceof Error ? err.message : "Hinzuf\u00fcgen fehlgeschlagen"
      )
    } finally {
      setAddSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api(`/inventory/${id}`, { method: "DELETE" })
      refreshItems(categoryFilter)
    } catch (err) {
      setError(err instanceof Error ? err.message : "L\u00f6schen fehlgeschlagen")
    }
  }

  const startEdit = (item: InventoryItem) => {
    setEditingItem(item)
    setEditQuantity(String(item.quantity))
    setEditUnit(item.unit)
    setEditExpiryDate(item.expiry_date || "")
    setEditCategory(item.category)
    setEditError("")
  }

  const handleEditSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!editingItem) return
    setEditError("")
    setEditSubmitting(true)
    try {
      await api(`/inventory/${editingItem.id}`, {
        method: "PUT",
        body: JSON.stringify({
          quantity: parseFloat(editQuantity),
          unit: editUnit,
          expiry_date: editExpiryDate || null,
          category: editCategory,
        }),
      })
      setEditingItem(null)
      refreshItems(categoryFilter)
    } catch (err) {
      setEditError(
        err instanceof Error ? err.message : "Aktualisierung fehlgeschlagen"
      )
    } finally {
      setEditSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="p-4 text-muted-foreground">Laden...</div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Vorrat"
        actions={
          <Button onClick={() => setShowAddForm(!showAddForm)}>
            {showAddForm ? "Abbrechen" : "+ Hinzuf\u00fcgen"}
          </Button>
        }
      />

      {/* Add form */}
      {showAddForm && (
        <form
          onSubmit={handleAddSubmit}
          className="mb-6 rounded-lg border p-6 space-y-4"
        >
          {addError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {addError}
            </div>
          )}

          <div className="space-y-2 relative">
            <label className="text-sm font-medium">Zutat</label>
            <input
              type="text"
              required
              value={addIngredientSearch}
              onChange={(e) => {
                setAddIngredientSearch(e.target.value)
                setAddIngredientId(null)
                setShowIngredientDropdown(true)
              }}
              onFocus={() => setShowIngredientDropdown(true)}
              onBlur={() =>
                setTimeout(() => setShowIngredientDropdown(false), 200)
              }
              placeholder="Zutat suchen..."
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
            {showIngredientDropdown && filteredIngredients.length > 0 && (
              <div className="absolute z-10 w-full rounded-md border bg-background shadow-lg max-h-40 overflow-auto">
                {filteredIngredients.map((ing) => (
                  <button
                    key={ing.id}
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
                    onMouseDown={() => {
                      setAddIngredientSearch(ing.name)
                      setAddIngredientId(ing.id)
                      setShowIngredientDropdown(false)
                    }}
                  >
                    {ing.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Menge</label>
              <input
                type="number"
                step="any"
                min="0"
                required
                value={addQuantity}
                onChange={(e) => setAddQuantity(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Einheit</label>
              <select
                value={addUnit}
                onChange={(e) => setAddUnit(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm bg-background"
              >
                {UNITS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Ablaufdatum (optional)</label>
            <input
              type="date"
              value={addExpiryDate}
              onChange={(e) => setAddExpiryDate(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Kategorie</label>
            <div className="flex gap-4">
              {(
                ["raw", "cooked", "frozen"] as const
              ).map((cat) => (
                <label key={cat} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="addCategory"
                    value={cat}
                    checked={addCategory === cat}
                    onChange={(e) => setAddCategory(e.target.value)}
                  />
                  {categoryLabel(cat)}
                </label>
              ))}
            </div>
          </div>

          <Button type="submit" disabled={addSubmitting} className="w-full">
            {addSubmitting ? "Wird hinzugef\u00fcgt..." : "Hinzuf\u00fcgen"}
          </Button>
        </form>
      )}

      {/* Error banner */}
      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Controls */}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Sortieren:</span>
          {(
            [
              ["expiry", "Ablaufdatum"],
              ["name", "Name"],
              ["category", "Kategorie"],
            ] as const
          ).map(([mode, label]) => (
            <button
              key={mode}
              onClick={() => setSortMode(mode as SortMode)}
              className={cn(
                "rounded-md px-2 py-1 text-sm",
                sortMode === mode
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted"
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Filter:</span>
          {(
            [
              ["all", "Alle"],
              ["raw", "Roh"],
              ["cooked", "Gekocht"],
              ["frozen", "Tiefgefroren"],
            ] as const
          ).map(([cat, label]) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat as CategoryFilter)}
              className={cn(
                "rounded-md px-2 py-1 text-sm",
                categoryFilter === cat
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted"
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border px-3 py-1 text-sm ml-auto w-48"
        />
      </div>

      {/* Item list */}
      {filteredItems.length === 0 ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
          Keine Vorräte vorhanden. Füge Zutaten hinzu, um deinen Vorrat zu
          verfolgen.
        </div>
      ) : (
        <div className="space-y-2">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className="rounded-lg border p-4 transition-colors hover:bg-muted/50"
            >
              {editingItem?.id === item.id ? (
                <form onSubmit={handleEditSubmit} className="space-y-3">
                  {editError && (
                    <div className="rounded-md bg-destructive/10 p-2 text-sm text-destructive">
                      {editError}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs font-medium">Menge</label>
                      <input
                        type="number"
                        step="any"
                        min="0"
                        required
                        value={editQuantity}
                        onChange={(e) => setEditQuantity(e.target.value)}
                        className="w-full rounded-md border px-2 py-1 text-sm"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-medium">Einheit</label>
                      <select
                        value={editUnit}
                        onChange={(e) => setEditUnit(e.target.value)}
                        className="w-full rounded-md border px-2 py-1 text-sm bg-background"
                      >
                        {UNITS.map((u) => (
                          <option key={u} value={u}>
                            {u}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium">Ablaufdatum</label>
                    <input
                      type="date"
                      value={editExpiryDate}
                      onChange={(e) => setEditExpiryDate(e.target.value)}
                      className="w-full rounded-md border px-2 py-1 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium">Kategorie</label>
                    <div className="flex gap-3">
                      {(["raw", "cooked", "frozen"] as const).map((cat) => (
                        <label
                          key={cat}
                          className="flex items-center gap-1 text-sm"
                        >
                          <input
                            type="radio"
                            name={`editCategory-${item.id}`}
                            value={cat}
                            checked={editCategory === cat}
                            onChange={(e) => setEditCategory(e.target.value)}
                          />
                          {categoryLabel(cat)}
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit" size="sm" disabled={editSubmitting}>
                      {editSubmitting ? "Speichern..." : "Speichern"}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setEditingItem(null)}
                    >
                      Abbrechen
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className="font-medium">
                        {item.ingredient_name}
                      </span>
                      <span
                        className={cn(
                          "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                          categoryBadgeClass(item.category)
                        )}
                      >
                        {categoryLabel(item.category)}
                      </span>
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {item.quantity} {item.unit}
                      <span className="mx-2">{"\u00b7"}</span>
                      <span className={getExpiryClass(item.expiry_date)}>
                        {item.expiry_date
                          ? `bis ${formatDate(item.expiry_date)}`
                          : "Kein Ablaufdatum"}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => startEdit(item)}
                    >
                      Bearbeiten
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDelete(item.id)}
                    >
                      {"L\u00f6schen"}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
