import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { FileDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/PageHeader"
import { generateWeekPlanPdf } from "@/lib/pdf-weekplan"
import {
  getCurrentIsoWeek,
  getIsoWeek,
  formatWeekLabel,
  isoWeekMonday,
} from "@/lib/iso-week"

interface Recipe {
  recipe_id: number
  title: string
  score: number
  matched_ingredients: number
  total_ingredients: number
  missing_ingredients: string[]
  urgency_boost: number
  expiring_ingredients: string[]
}

interface LeftoverItem {
  id: number
  ingredient_name: string
  quantity: number
  unit: string
  category: string
  source_recipe_id: number | null
  source_week_plan_id: number | null
}

interface MealSlot {
  id: number
  week_plan_id: number
  meal_type: string
  day_of_week: number
  active: boolean
  recipe_id: number | null
  recipe_title: string | null
  portions: number
  dietary_filter_tag_id: number | null
  cooked: boolean
}

interface WeekData {
  id: number
  household_id: number
  year: number
  iso_week: number
  is_public: boolean
  slots: MealSlot[]
}

const DAY_LABELS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
const MEAL_LABELS: Record<string, string> = {
  breakfast: "Frühstück",
  lunch: "Mittag",
  dinner: "Abend",
  dessert: "Dessert",
}
const MEAL_TYPES = ["breakfast", "lunch", "dinner", "dessert"]

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

function isCurrentOrFuture(year: number, week: number): boolean {
  const [cy, cw] = getCurrentIsoWeek()
  if (year > cy) return true
  if (year === cy && week >= cw && week <= cw + 4) return true
  return false
}

export default function WeekPlanPage() {
  const [cy, cw] = getCurrentIsoWeek()
  const [weekData, setWeekData] = useState<WeekData | null>(null)
  const [suggestions, setSuggestions] = useState<Recipe[]>([])
  const [leftovers, setLeftovers] = useState<LeftoverItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [activeMode, setActiveMode] = useState<string>("partial")
  const [selectedDay, setSelectedDay] = useState<number>(0)
  const [selectedMeal, setSelectedMeal] = useState<string>("lunch")
  const [dragOverDay, setDragOverDay] = useState<number | null>(null)
  const [dragOverMeal, setDragOverMeal] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [year, setYear] = useState<number>(cy)
  const [isoWeek, setIsoWeek] = useState<number>(cw)
  const [editable, setEditable] = useState(true)
  const [copied, setCopied] = useState(false)
  const [cookConfirm, setCookConfirm] = useState<number | null>(null)
  const [leftoverSlot, setLeftoverSlot] = useState<{id: number; title: string} | null>(null)
  const [leftoverPortions, setLeftoverPortions] = useState(2)
  const [householdSlug, setHouseholdSlug] = useState("")
  const [publicSaving, setPublicSaving] = useState(false)
  const [pdfGenerating, setPdfGenerating] = useState(false)
  const [recipeSearch, setRecipeSearch] = useState("")
  const [searchResults, setSearchResults] = useState<Recipe[]>([])
  const navigate = useNavigate()

  const refreshAll = useCallback(() => {
    let cancelled = false
    Promise.all([
      api(`/weeks/${year}/${isoWeek}`),
      api("/match", {
        method: "POST",
        body: JSON.stringify({
          mode: activeMode,
          current_plan_reservations: null,
        }),
      }),
      api("/inventory?category=cooked"),
      api("/household"),
    ])
      .then(([weekResult, matchResult, leftoversResult, householdResult]) => {
        if (!cancelled) {
          setWeekData(weekResult as WeekData)
          setEditable(isCurrentOrFuture(year, isoWeek))
          setSuggestions(matchResult.suggestions || [])
          setLeftovers(
            (leftoversResult as LeftoverItem[]) || []
          )
          setHouseholdSlug((householdResult as { slug: string }).slug || "")
          setError("")
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          if (err.message.includes("not found")) {
            setWeekData(null)
            setSuggestions([])
          } else {
            setError(err.message || "Failed to load week")
          }
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [year, isoWeek, activeMode])

  useEffect(() => {
    const cancel = refreshAll()
    return cancel
  }, [refreshAll])

  const searchTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const searchRecipes = (query: string) => {
    setRecipeSearch(query)
    clearTimeout(searchTimer.current)
    if (query.trim().length < 2) {
      setSearchResults([])
      return
    }
    searchTimer.current = setTimeout(() => {
      api(`/recipes?search=${encodeURIComponent(query.trim())}&limit=20`)
        .then((data: { id: number; title: string; ingredients?: { length: number } }[]) =>
          setSearchResults(
            data.map((item) => ({
              recipe_id: item.id,
              title: item.title,
              score: 0,
              matched_ingredients: 0,
              total_ingredients: item.ingredients?.length ?? 0,
              missing_ingredients: [],
              urgency_boost: 0,
              expiring_ingredients: [],
            }))
          )
        )
        .catch(() => setSearchResults([]))
    }, 250)
  }

  const navigateWeek = (delta: number) => {
    setLoading(true)
    const monday = isoWeekMonday(year, isoWeek)
    monday.setDate(monday.getDate() + delta * 7)
    const [newYear, newWeek] = getIsoWeek(monday)
    setYear(newYear)
    setIsoWeek(newWeek)
  }

  const goToToday = () => {
    setLoading(true)
    const [tcy, tcw] = getCurrentIsoWeek()
    setYear(tcy)
    setIsoWeek(tcw)
  }

  const planRecipe = async (day: number, meal: string, recipeId: number) => {
    if (!editable) return
    setSaving(true)
    try {
      await api(`/weeks/${year}/${isoWeek}/slots`, {
        method: "PUT",
        body: JSON.stringify({
          slots: [{ day_of_week: day, meal_type: meal, recipe_id: recipeId }],
        }),
      })
      refreshAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to plan recipe")
    } finally {
      setSaving(false)
    }
  }

  const unplanRecipe = async (slotId: number) => {
    if (!editable) return
    setSaving(true)
    try {
      await api(`/weeks/${year}/${isoWeek}/slots/${slotId}/recipe`, {
        method: "DELETE",
      })
      refreshAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unplan recipe")
    } finally {
      setSaving(false)
    }
  }

  const updatePortions = async (
    day: number, meal: string, portions: number
  ) => {
    if (!editable) return
    setSaving(true)
    try {
      await api(`/weeks/${year}/${isoWeek}/slots`, {
        method: "PUT",
        body: JSON.stringify({
          slots: [{ day_of_week: day, meal_type: meal, portions }],
        }),
      })
      refreshAll()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to update portions"
      )
    } finally {
      setSaving(false)
    }
  }

  const moveRecipe = async (
    sourceSlotId: number,
    targetDay: number,
    targetMeal: string,
    recipeId: number
  ) => {
    if (!editable) return
    setSaving(true)
    try {
      await api(`/weeks/${year}/${isoWeek}/slots`, {
        method: "PUT",
        body: JSON.stringify({
          slots: [{ day_of_week: targetDay, meal_type: targetMeal, recipe_id: recipeId }],
        }),
      })
      await api(`/weeks/${year}/${isoWeek}/slots/${sourceSlotId}/recipe`, {
        method: "DELETE",
      })
      refreshAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to move recipe")
    } finally {
      setSaving(false)
    }
  }

  const createWeek = async (copyFromPrevious: boolean) => {
    setSaving(true)
    try {
      await api("/weeks", {
        method: "POST",
        body: JSON.stringify({
          year,
          iso_week: isoWeek,
          copy_from_previous: copyFromPrevious,
        }),
      })
      refreshAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create week")
    } finally {
      setSaving(false)
    }
  }

  const copyPublicLink = () => {
    if (!weekData || !householdSlug) return
    const url = `${window.location.origin}/plan/${householdSlug}/${year}/kw${isoWeek}`
    navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const generatePdf = async () => {
    if (!weekData || pdfGenerating) return
    setPdfGenerating(true)
    try {
      await generateWeekPlanPdf({
        weekLabel: formatWeekLabel(year, isoWeek),
        slots: weekData.slots
          .filter((s) => s.recipe_id !== null && s.recipe_title)
          .map((s) => ({
            dayOfWeek: s.day_of_week,
            mealType: s.meal_type,
            recipeTitle: s.recipe_title!,
            portions: s.portions,
          })),
        publicUrl: weekData.is_public && householdSlug
          ? `${window.location.origin}/plan/${householdSlug}/${year}/kw${isoWeek}`
          : null,
        fileName: `wochenplan-kw${isoWeek}-${year}.pdf`,
      })
    } finally {
      setPdfGenerating(false)
    }
  }

  const toggleWeekVisibility = async () => {
    if (!weekData) return
    setPublicSaving(true)
    try {
      const res = await api(
        `/weeks/${year}/${isoWeek}/visibility`,
        {
          method: "PUT",
          body: JSON.stringify({ is_public: !weekData.is_public }),
        }
      )
      setWeekData({ ...weekData, is_public: res.is_public })
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to update visibility"
      )
    } finally {
      setPublicSaving(false)
    }
  }

  const cookSlot = async (slotId: number) => {
    setSaving(true)
    setCookConfirm(null)
    try {
      await api(`/weeks/${year}/${isoWeek}/slots/${slotId}/cook`, {
        method: "POST",
      })
      setLeftoverSlot({
        id: slotId,
        title: getSlotSlotTitle(slotId) || "",
      })
      refreshAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cook")
    } finally {
      setSaving(false)
    }
  }

  const submitLeftovers = async () => {
    if (!leftoverSlot) return
    setSaving(true)
    try {
      await api(
        `/weeks/${year}/${isoWeek}/slots/${leftoverSlot.id}/leftovers`,
        {
          method: "POST",
          body: JSON.stringify({ portions_count: leftoverPortions }),
        }
      )
      setLeftoverSlot(null)
      setLeftoverPortions(2)
      refreshAll()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save leftovers"
      )
    } finally {
      setSaving(false)
    }
  }

  const skipLeftovers = () => {
    setLeftoverSlot(null)
    setLeftoverPortions(2)
  }

  const getSlotSlotTitle = (slotId: number): string | null => {
    if (!weekData) return null
    const slot = weekData.slots.find((s) => s.id === slotId)
    return slot?.recipe_title || null
  }

  const getSlot = (day: number, meal: string): MealSlot | undefined => {
    if (!weekData) return undefined
    return weekData.slots.find(
      (s) => s.day_of_week === day && s.meal_type === meal
    )
  }

  const handleDragStart = (recipe: Recipe) => (e: React.DragEvent) => {
    e.dataTransfer.setData("recipe_id", String(recipe.recipe_id))
    e.dataTransfer.setData("recipe_title", recipe.title)
    e.dataTransfer.effectAllowed = "move"
  }

  const handleSlotDrop =
    (day: number, meal: string) => (e: React.DragEvent) => {
      e.preventDefault()
      setDragOverDay(null)
      setDragOverMeal(null)
      const recipeId = parseInt(e.dataTransfer.getData("recipe_id") || "0")
      if (recipeId <= 0) return
      const sourceSlotId = parseInt(e.dataTransfer.getData("source_slot_id") || "0")
      if (sourceSlotId > 0) {
        moveRecipe(sourceSlotId, day, meal, recipeId)
      } else {
        planRecipe(day, meal, recipeId)
      }
    }

  const handleSlotDragOver =
    (
      day: number,
      meal: string,
      slot: MealSlot | undefined
    ) =>
    (e: React.DragEvent) => {
      e.preventDefault()
      if (!editable) return
      if (slot && slot.recipe_id !== null) return
      setDragOverDay(day)
      setDragOverMeal(meal)
    }

  const handleSlotDragLeave = () => {
    setDragOverDay(null)
    setDragOverMeal(null)
  }

  const handleSlotDragStart = (slot: MealSlot) => (e: React.DragEvent) => {
    e.dataTransfer.setData("recipe_id", String(slot.recipe_id))
    e.dataTransfer.setData("recipe_title", slot.recipe_title || "")
    e.dataTransfer.setData("source_slot_id", String(slot.id))
    e.dataTransfer.effectAllowed = "move"
  }

  if (loading) {
    return (
      <p className="p-4 text-muted-foreground">Laden...</p>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader title="Wochenplan" />
      <div className="flex items-center gap-3 p-3 border-b bg-muted/30">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigateWeek(-1)}
          disabled={saving}
        >
          ←
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={goToToday}
          disabled={saving}
        >
          Heute
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigateWeek(1)}
          disabled={saving}
        >
          →
        </Button>
        <span className="text-lg font-semibold">
          {formatWeekLabel(year, isoWeek)}
        </span>
        {!editable && (
          <span className="ml-2 rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            Archiv
          </span>
        )}
        <div className="ml-auto flex gap-1 items-center">
          {editable && (
            <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
              <input
                type="checkbox"
                checked={weekData?.is_public ?? false}
                onChange={toggleWeekVisibility}
                disabled={publicSaving}
                className="h-3.5 w-3.5"
              />
              Öffentlich
            </label>
          )}
          {weekData?.is_public && (
            <Button variant="outline" size="sm" onClick={copyPublicLink}>
              {copied ? "Kopiert!" : "Link kopieren"}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={generatePdf}
            disabled={pdfGenerating}
          >
            <FileDown className="h-4 w-4" />
            {pdfGenerating ? "..." : "PDF"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="mx-3 mt-2 rounded-md bg-destructive/10 p-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {!weekData && !loading && (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center space-y-4">
            <p className="text-muted-foreground">
              Kein Plan für {formatWeekLabel(year, isoWeek)}
            </p>
            <div className="flex gap-2 justify-center">
              <Button onClick={() => createWeek(false)} disabled={saving}>
                {saving ? "..." : "Leere Woche"}
              </Button>
              <Button
                variant="outline"
                onClick={() => createWeek(true)}
                disabled={saving}
              >
                {saving ? "..." : "Kopie der Vorwoche"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {weekData && (
        <div className="flex flex-1 overflow-hidden">
          <div className="flex-[7] overflow-auto p-3">
            <div className="grid grid-cols-8 gap-1">
              <div className="font-medium text-sm text-muted-foreground p-1" />
              {DAY_LABELS.map((day) => (
                <div
                  key={day}
                  className="text-center font-medium text-sm p-1 text-muted-foreground"
                >
                  {day}
                </div>
              ))}
              {MEAL_TYPES.map((meal) =>
                DAY_LABELS.map((_, dayIdx) => {
                  const slot = getSlot(dayIdx, meal)
                  const isActive = slot?.active !== false
                  const isDraggedOver =
                    dragOverDay === dayIdx && dragOverMeal === meal
                  const isSelected =
                    selectedDay === dayIdx && selectedMeal === meal

                  return (
                    <div key={`${meal}-${dayIdx}`} className="contents">
                      {dayIdx === 0 && (
                        <div className="text-sm font-medium p-1 flex items-center">
                          {MEAL_LABELS[meal]}
                        </div>
                      )}
                      <div
                        draggable={!!(slot?.recipe_id && editable && !slot.cooked)}
                        onDragStart={
                          slot?.recipe_id && editable && !slot.cooked
                            ? handleSlotDragStart(slot)
                            : undefined
                        }
                        className={[
                          "rounded border p-1 min-h-[70px] text-xs cursor-default",
                          isActive && editable
                            ? "bg-background hover:border-primary/50"
                            : "bg-muted/40 text-muted-foreground",
                          isDraggedOver && editable
                            ? "border-primary bg-primary/5 ring-1 ring-primary"
                            : "border-border",
                          !editable ? "pointer-events-none" : "",
                          isSelected ? "ring-1 ring-ring" : "",
                        ].join(" ")}
                        onClick={() => {
                          if (!isActive || !editable) return
                          setSelectedDay(dayIdx)
                          setSelectedMeal(meal)
                        }}
                        onDrop={
                          isActive
                            ? handleSlotDrop(dayIdx, meal)
                            : (e: React.DragEvent) => e.preventDefault()
                        }
                        onDragOver={
                          isActive
                            ? handleSlotDragOver(dayIdx, meal, slot)
                            : undefined
                        }
                        onDragLeave={handleSlotDragLeave}
                      >
                        {slot?.recipe_id ? (
                          <div className="flex flex-col items-center gap-1">
                            {slot.cooked && (
                              <span className="text-green-600 text-xs font-bold">
                                ✓ Gekocht
                              </span>
                            )}
                            <span className="font-medium truncate w-full text-center">
                              {slot.recipe_title || `#${slot.recipe_id}`}
                            </span>
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                min={1}
                                className="w-10 rounded border px-1 text-center text-xs"
                                value={slot.portions}
                                onChange={(e) => {
                                  const v = Math.max(
                                    1,
                                    parseInt(e.target.value) || 1
                                  )
                                  updatePortions(dayIdx, meal, v)
                                }}
                                disabled={!editable || saving || slot.cooked}
                              />
                              <span className="text-muted-foreground">Port.</span>
                            </div>
                            {editable && !slot.cooked && (
                              <div className="flex gap-1 mt-0.5">
                                <button
                                  className="text-primary hover:underline text-xs"
                                  onClick={() =>
                                    navigate(
                                      `/recipes/${slot.recipe_id}/cook?portions=${slot.portions}&slotId=${slot.id}&year=${year}&isoWeek=${isoWeek}`,
                                    )
                                  }
                                >
                                  Kochmodus
                                </button>
                                <button
                                  className="text-green-600 hover:underline text-xs"
                                  onClick={() => setCookConfirm(slot.id)}
                                >
                                  Gekocht
                                </button>
                                <button
                                  className="text-destructive hover:underline"
                                  onClick={() => unplanRecipe(slot.id)}
                                >
                                  ✕
                                </button>
                              </div>
                            )}
                          </div>
                        ) : isActive && editable ? (
                          <div className="flex items-center justify-center h-full text-muted-foreground">
                            +
                          </div>
                        ) : (
                          <div className="flex items-center justify-center h-full text-muted-foreground">
                            —
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>

          <div className="flex-[3] border-l overflow-auto p-3">
            <h2 className="font-semibold mb-2">Vorschläge</h2>

            <input
              type="text"
              placeholder="Menü suchen..."
              value={recipeSearch}
              onChange={(e) => searchRecipes(e.target.value)}
              className="w-full rounded-md border px-3 py-1.5 text-sm mb-3"
            />

            {recipeSearch.trim().length >= 2 && (
              <div className="space-y-2 mb-3">
                {searchResults.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    Keine Menüs gefunden.
                  </p>
                )}
                {searchResults.map((recipe) => (
                  <div
                    key={`search-${recipe.recipe_id}`}
                    className="rounded border p-2 text-sm cursor-grab active:cursor-grabbing hover:border-primary/50"
                    draggable={editable}
                    onDragStart={handleDragStart(recipe)}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium truncate">{recipe.title}</span>
                    </div>
                    <div className="flex gap-2 mt-1 text-xs text-muted-foreground">
                      <span>{recipe.matched_ingredients}/{recipe.total_ingredients} Zutaten</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-1 mb-3">
              {[
                { key: "exact", label: "Exakt" },
                { key: "partial", label: "Teilweise" },
                { key: "ingredient_first", label: "Zutat" },
              ].map((mode) => (
                <Button
                  key={mode.key}
                  variant={activeMode === mode.key ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveMode(mode.key)}
                >
                  {mode.label}
                </Button>
              ))}
            </div>

            <div className="space-y-2">
              {suggestions.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Keine Vorschläge. Füge Rezepte und Vorräte hinzu.
                </p>
              )}
              {suggestions.map((recipe) => (
                <div
                  key={recipe.recipe_id}
                  className="rounded border p-2 text-sm cursor-grab active:cursor-grabbing hover:border-primary/50"
                  draggable={editable}
                  onDragStart={handleDragStart(recipe)}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium truncate">{recipe.title}</span>
                    <span className="ml-2 text-xs font-mono text-muted-foreground">
                      {Math.round(recipe.score * 100)}%
                    </span>
                  </div>
                  <div className="flex gap-2 mt-1 text-xs text-muted-foreground">
                    <span>
                      {recipe.matched_ingredients}/{recipe.total_ingredients}{" "}
                      Zutaten
                    </span>
                    {recipe.urgency_boost > 0 && (
                      <span className="text-orange-500 font-medium">
                        ⚠ Dringend
                      </span>
                    )}
                  </div>
                  {recipe.missing_ingredients.length > 0 && (
                    <div className="mt-1 text-xs text-destructive">
                      Fehlt: {recipe.missing_ingredients.join(", ")}
                    </div>
                  )}
                  {recipe.expiring_ingredients.length > 0 && (
                    <div className="mt-1 text-xs text-orange-600">
                      Läuft bald ab:{" "}
                      {recipe.expiring_ingredients.join(", ")}
                    </div>
                  )}
                </div>
              ))}
              {leftovers.length > 0 && (
                <>
                  <h3 className="text-xs font-semibold text-muted-foreground mt-3">
                    Resten
                  </h3>
                  {leftovers.map((item) => (
                    <div
                      key={`leftover-${item.id}`}
                      className="rounded border p-2 text-sm bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800"
                    >
                      <span className="font-medium truncate">
                        {item.ingredient_name}
                      </span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        — {item.quantity} {item.unit === "Stück" ? "Portionen" : item.unit}
                      </span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {cookConfirm !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-background rounded-lg shadow-lg p-6 w-80 space-y-3">
            <p className="font-medium">Zutaten vom Vorrat abbuchen?</p>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCookConfirm(null)}
              >
                Abbrechen
              </Button>
              <Button
                size="sm"
                onClick={() => cookSlot(cookConfirm)}
                disabled={saving}
              >
                {saving ? "..." : "Bestätigen"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {leftoverSlot !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-background rounded-lg shadow-lg p-6 w-80 space-y-3">
            <p className="font-medium">
              Portionen Resten von &quot;{leftoverSlot.title}&quot;?
            </p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                className="w-16 rounded border px-2 py-1 text-sm text-center"
                value={leftoverPortions}
                onChange={(e) =>
                  setLeftoverPortions(
                    Math.max(1, parseInt(e.target.value) || 1)
                  )
                }
              />
              <span className="text-sm text-muted-foreground">Portionen</span>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={skipLeftovers}>
                Überspringen
              </Button>
              <Button
                size="sm"
                onClick={submitLeftovers}
                disabled={saving}
              >
                {saving ? "..." : "Speichern"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
