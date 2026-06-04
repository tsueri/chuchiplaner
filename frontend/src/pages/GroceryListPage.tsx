import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import { PageHeader } from "@/components/PageHeader"

interface RecipeBreakdownEntry {
  recipe_id: number
  recipe_title: string
  quantity: number
  unit: string
}

interface GroceryListItem {
  id: number
  grocery_list_id: number
  ingredient_id: number | null
  name: string
  quantity: number
  unit: string
  checked: boolean
  recipe_breakdown: RecipeBreakdownEntry[] | null
}

interface GroceryListData {
  id: number
  household_id: number
  week_plan_id: number | null
  share_token: string | null
  created_at: string | null
  completed_at: string | null
  items: GroceryListItem[]
}

const UNITS = ["g", "kg", "ml", "l", "EL", "TL", "St\u00fcck", "Bund", "Prise", "Msp", "Packung"]

async function api(path: string, options?: RequestInit) {
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!res.ok && res.status !== 204) {
    const data = await res.json().catch(() => ({ detail: "Request failed" }))
    throw new Error(data.detail || "Request failed")
  }
  if (res.status === 204) return null
  return res.json()
}

export default function GroceryListPage() {
  const [listData, setListData] = useState<GroceryListData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)
  const [expandedItem, setExpandedItem] = useState<number | null>(null)
  const [editingItem, setEditingItem] = useState<number | null>(null)
  const [editQuantity, setEditQuantity] = useState(0)
  const [editUnit, setEditUnit] = useState("")
  const [showAddForm, setShowAddForm] = useState(false)
  const [newName, setNewName] = useState("")
  const [newQuantity, setNewQuantity] = useState(1)
  const [newUnit, setNewUnit] = useState("St\u00fcck")
  const [showCompleteDialog, setShowCompleteDialog] = useState(false)
  const [weekPlans, setWeekPlans] = useState<Array<{id:number;year:number;iso_week:number}>>([])
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null)

  const refreshList = useCallback(() => {
    let cancelled = false
    const params = selectedPlanId ? `?week_plan_id=${selectedPlanId}` : ""
    api(`/grocery-list${params}`)
      .then((data) => {
        if (!cancelled) {
          setListData(data)
          setError("")
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "Failed to load")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [selectedPlanId])

  useEffect(() => {
    const cancel = refreshList()
    return cancel
  }, [refreshList])

  useEffect(() => {
    let cancelled = false
    api("/weeks").then((data) => {
      if (!cancelled) {
        const plans = data || []
        setWeekPlans(plans)
        if (plans.length > 0 && selectedPlanId === null) {
          setSelectedPlanId(plans[0].id)
        }
      }
    }).catch(() => {})
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const toggleCheck = async (itemId: number, checked: boolean) => {
    setSaving(true)
    try {
      await api(`/grocery-list/items/${itemId}`, {
        method: "PUT",
        body: JSON.stringify({ checked: !checked }),
      })
      refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update")
    } finally {
      setSaving(false)
    }
  }

  const saveEdit = async (itemId: number) => {
    setSaving(true)
    try {
      await api(`/grocery-list/items/${itemId}`, {
        method: "PUT",
        body: JSON.stringify({ quantity: editQuantity, unit: editUnit }),
      })
      setEditingItem(null)
      refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update")
    } finally {
      setSaving(false)
    }
  }

  const deleteItem = async (itemId: number) => {
    setSaving(true)
    try {
      await api(`/grocery-list/items/${itemId}`, { method: "DELETE" })
      refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete")
    } finally {
      setSaving(false)
    }
  }

  const addItem = async () => {
    if (!newName.trim() || !listData) return
    setSaving(true)
    try {
      await api(`/grocery-list/items?list_id=${listData.id}`, {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          quantity: newQuantity,
          unit: newUnit,
        }),
      })
      setNewName("")
      setNewQuantity(1)
      setNewUnit("St\u00fcck")
      setShowAddForm(false)
      refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add")
    } finally {
      setSaving(false)
    }
  }

  const regenerate = async () => {
    setSaving(true)
    try {
      const params = selectedPlanId ? `?week_plan_id=${selectedPlanId}` : ""
      await api(`/grocery-list/generate${params}`, { method: "POST" })
      refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to regenerate")
    } finally {
      setSaving(false)
    }
  }

  const copyShareLink = async () => {
    if (!listData) return
    try {
      const res = await api(`/grocery-list/${listData.id}/share`)
      const url = `${window.location.origin}/grocery-list/share/${res.token}`
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate share link")
    }
  }

  const completeList = async () => {
    if (!listData) return
    setSaving(true)
    setShowCompleteDialog(false)
    try {
      await api(`/grocery-list/complete?list_id=${listData.id}`, {
        method: "POST",
      })
      refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete")
    } finally {
      setSaving(false)
    }
  }

  const startEdit = (item: GroceryListItem) => {
    setEditingItem(item.id)
    setEditQuantity(item.quantity)
    setEditUnit(item.unit)
  }

  const uncheckedCount = listData?.items.filter((i) => !i.checked).length ?? 0
  const totalCount = listData?.items.length ?? 0
  const progress = totalCount > 0 ? (totalCount - uncheckedCount) / totalCount * 100 : 0

  if (loading && !listData) {
    return (
      <div className="p-4 text-muted-foreground">Laden...</div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Einkaufsliste"
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={regenerate}
              disabled={saving}
            >
              Neu laden
            </Button>
            {listData && (
              <Button
                variant="outline"
                size="sm"
                onClick={copyShareLink}
                disabled={saving}
              >
                {copied ? "Kopiert!" : "Teilen"}
              </Button>
            )}
            {!listData?.completed_at && listData && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCompleteDialog(true)}
                disabled={saving}
              >
                Erledigt
              </Button>
            )}
          </>
        }
      />

      {weekPlans.length > 0 && (
        <div className="mb-4">
          <select
            className="rounded border p-2 text-sm bg-background"
            value={selectedPlanId ?? ""}
            onChange={(e) => setSelectedPlanId(
              e.target.value ? parseInt(e.target.value) : null
            )}
          >
            <option value="">Kein Wochenplan</option>
            {weekPlans.map((p) => (
              <option key={p.id} value={p.id}>
                KW {p.iso_week}, {p.year}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <div className="mb-3 rounded-md bg-destructive/10 p-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {listData?.completed_at && (
        <div className="mb-4 rounded-md bg-green-50 dark:bg-green-950 p-3 text-sm text-green-700 dark:text-green-300">
          Erledigt am{" "}
          {new Date(listData.completed_at).toLocaleDateString("de-DE", {
            day: "numeric",
            month: "long",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
          {" \u2014 "}
          <Button variant="link" size="sm" className="p-0 h-auto text-sm" onClick={regenerate}>
            Neue Liste erstellen
          </Button>
        </div>
      )}

      <div className="mb-4">
        <div className="flex items-center justify-between text-sm text-muted-foreground mb-1">
          <span>
            {uncheckedCount === 0 && totalCount > 0
              ? "Alles erledigt"
              : `${uncheckedCount} von ${totalCount} offen`}
          </span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              progress === 100 ? "bg-green-500" : "bg-primary"
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {listData && (
        <div className="space-y-1">
          {listData.items.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">
              Keine Einträge. Plane Rezepte im Wochenplan, um eine
              Einkaufsliste zu erstellen.
            </p>
          )}

          {listData.items
            .sort((a, b) => {
              if (a.checked !== b.checked) return a.checked ? 1 : -1
              return a.name.localeCompare(b.name)
            })
            .map((item) => (
              <div key={item.id} className="border rounded-lg overflow-hidden">
                <div
                  className={cn(
                    "flex items-center gap-3 p-3 hover:bg-muted/30 cursor-pointer",
                    item.checked && "opacity-50"
                  )}
                  onClick={() => toggleCheck(item.id, item.checked)}
                >
                  <input
                    type="checkbox"
                    checked={item.checked}
                    onChange={() => {}}
                    className="w-5 h-5 accent-primary cursor-pointer"
                  />
                  <span
                    className={cn(
                      "flex-1 font-medium",
                      item.checked && "line-through"
                    )}
                  >
                    {item.name}
                  </span>

                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (editingItem === item.id) {
                        setEditingItem(null)
                      } else {
                        startEdit(item)
                      }
                    }}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    {item.quantity} {item.unit}
                  </button>

                  {item.recipe_breakdown &&
                    item.recipe_breakdown.length > 0 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setExpandedItem(
                            expandedItem === item.id ? null : item.id
                          )
                        }}
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        {expandedItem === item.id ? "\u25B2" : "\u25BC"}
                      </button>
                    )}

                  {item.ingredient_id === null && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteItem(item.id)
                      }}
                      className="text-destructive text-xs hover:underline"
                    >
                      ✕
                    </button>
                  )}
                </div>

                {editingItem === item.id && (
                  <div className="px-3 pb-3 flex items-center gap-2 border-t pt-2">
                    <input
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={editQuantity}
                      onChange={(e) =>
                        setEditQuantity(parseFloat(e.target.value) || 0)
                      }
                      className="w-20 rounded border p-1 text-sm text-center"
                    />
                    <select
                      value={editUnit}
                      onChange={(e) => setEditUnit(e.target.value)}
                      className="rounded border p-1 text-sm"
                    >
                      {UNITS.map((u) => (
                        <option key={u} value={u}>
                          {u}
                        </option>
                      ))}
                    </select>
                    <Button size="sm" onClick={() => saveEdit(item.id)}>
                      Speichern
                    </Button>
                  </div>
                )}

                {expandedItem === item.id &&
                  item.recipe_breakdown &&
                  item.recipe_breakdown.length > 0 && (
                    <div className="px-3 pb-3 border-t pt-2 text-xs text-muted-foreground">
                      {item.recipe_breakdown.map((rb, i) => (
                        <div key={i} className="flex justify-between py-0.5">
                          <span>{rb.recipe_title}</span>
                          <span>
                            {rb.quantity} {rb.unit}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
              </div>
            ))}
        </div>
      )}

      {listData && !listData.completed_at && (
        <div className="mt-4">
          {!showAddForm ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAddForm(true)}
            >
              + Extra Artikel
            </Button>
          ) : (
            <div className="flex items-center gap-2 p-3 border rounded-lg">
              <input
                type="text"
                placeholder="Name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="flex-1 rounded border p-1 text-sm"
              />
              <input
                type="number"
                min={1}
                value={newQuantity}
                onChange={(e) =>
                  setNewQuantity(parseInt(e.target.value) || 1)
                }
                className="w-16 rounded border p-1 text-sm text-center"
              />
              <select
                value={newUnit}
                onChange={(e) => setNewUnit(e.target.value)}
                className="rounded border p-1 text-sm"
              >
                {UNITS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
              <Button size="sm" onClick={addItem}>
                Hinzufügen
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAddForm(false)}
              >
                ✕
              </Button>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2 mt-6 justify-center">
        <Link to="/plan">
          <Button variant="outline" size="sm">
            ← Wochenplan
          </Button>
        </Link>
      </div>

      {showCompleteDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-background rounded-lg shadow-lg p-6 w-80 space-y-3">
            <p className="font-medium">
              Einkaufsliste als erledigt markieren?
            </p>
            <p className="text-sm text-muted-foreground">
              Abgehakte Artikel werden in den Vorrat übertragen.
            </p>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowCompleteDialog(false)}
              >
                Abbrechen
              </Button>
              <Button size="sm" onClick={completeList} disabled={saving}>
                {saving ? "..." : "Ja, erledigt"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
