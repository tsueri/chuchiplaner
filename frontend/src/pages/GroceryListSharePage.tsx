import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"

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

interface ShareData {
  id: number
  household_name: string
  week_label: string
  items: GroceryListItem[]
  completed_at: string | null
}

async function api(path: string) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
  })
  if (!res.ok) {
    throw new Error("Not found")
  }
  return res.json()
}

export default function GroceryListSharePage() {
  const { token } = useParams<{ token: string }>()
  const [data, setData] = useState<ShareData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [expandedItem, setExpandedItem] = useState<number | null>(null)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    api(`/grocery-list/share/${token}`)
      .then((result) => {
        if (!cancelled) {
          setData(result)
          setError("")
        }
      })
      .catch(() => {
        if (!cancelled) setError("Link nicht gefunden oder abgelaufen")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [token])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Laden...</p>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center space-y-2">
          <p className="text-destructive">{error || "Nicht gefunden"}</p>
        </div>
      </div>
    )
  }

  const unchecked = data.items.filter((i) => !i.checked).length
  const total = data.items.length

  return (
    <div className="min-h-screen bg-background text-foreground p-4 max-w-2xl mx-auto">
      <div className="mb-4">
        <h1 className="text-xl font-bold">Einkaufsliste</h1>
        {data.household_name && (
          <p className="text-sm text-muted-foreground">{data.household_name}</p>
        )}
        {data.week_label && (
          <p className="text-sm text-muted-foreground">{data.week_label}</p>
        )}
        {data.completed_at && (
          <p className="text-xs text-green-600 mt-1">
            Erledigt am{" "}
            {new Date(data.completed_at).toLocaleDateString("de-DE")}
          </p>
        )}
        {total > 0 && (
          <p className="text-xs text-muted-foreground mt-1">
            {unchecked} von {total} offen
          </p>
        )}
      </div>

      {data.items.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-8">
          Keine Einträge
        </p>
      )}

      <div className="space-y-1">
        {data.items
          .sort((a, b) => {
            if (a.checked !== b.checked) return a.checked ? 1 : -1
            return a.name.localeCompare(b.name)
          })
          .map((item) => (
            <div key={item.id} className="border rounded-lg overflow-hidden">
              <div className="flex items-center gap-3 p-3">
                <div
                  className={`w-5 h-5 border-2 rounded ${
                    item.checked
                      ? "bg-green-500 border-green-500"
                      : "border-muted-foreground/30"
                  }`}
                />
                <span className="flex-1 font-medium">
                  {item.name}
                </span>
                <span className="text-sm text-muted-foreground">
                  {item.quantity} {item.unit}
                </span>
                {item.recipe_breakdown &&
                  item.recipe_breakdown.length > 0 && (
                    <button
                      onClick={() =>
                        setExpandedItem(
                          expandedItem === item.id ? null : item.id
                        )
                      }
                      className="text-xs text-muted-foreground"
                    >
                      {expandedItem === item.id ? "\u25B2" : "\u25BC"}
                    </button>
                  )}
              </div>

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

      <div className="mt-8 text-center">
        <p className="text-xs text-muted-foreground">
          Erstellt mit Chuchiplaner
        </p>
      </div>
    </div>
  )
}
