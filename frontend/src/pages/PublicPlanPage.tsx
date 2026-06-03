import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"

interface PublicRecipe {
  id: number
  title: string
  image_url: string | null
  source_url: string | null
  source_domain: string | null
  servings: number
}

interface PublicSlot {
  id: number
  meal_type: string
  day_of_week: number
  active: boolean
  recipe: PublicRecipe | null
  portions: number
  cooked: boolean
}

interface PublicPlan {
  household_name: string
  household_slug: string
  year: number
  iso_week: number
  slots: PublicSlot[]
}

const DAY_LABELS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
const MEAL_LABELS: Record<string, string> = {
  breakfast: "Fruehstueck",
  lunch: "Mittag",
  dinner: "Abend",
  dessert: "Dessert",
}
const MEAL_TYPES = ["breakfast", "lunch", "dinner", "dessert"]

function formatWeekLabel(year: number, week: number): string {
  const firstDay = new Date(year, 0, 4)
  const dayOfWeek = firstDay.getDay() || 7
  const monday = new Date(firstDay)
  monday.setDate(firstDay.getDate() - dayOfWeek + 1 + (week - 1) * 7)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  return `KW ${week}, ${monday.getDate()}.–${sunday.getDate()}.${sunday.getMonth() + 1}.`
}

const DOMAIN_COLORS: Record<string, string> = {
  "fooby.ch": "bg-emerald-100 text-emerald-800",
  "migusto.ch": "bg-orange-100 text-orange-800",
  "bettybossi.ch": "bg-purple-100 text-purple-800",
  "swissmilk.ch": "bg-blue-100 text-blue-800",
  "marmiton.org": "bg-rose-100 text-rose-800",
  "chefkoch.de": "bg-amber-100 text-amber-800",
  "lemenu.ch": "bg-teal-100 text-teal-800",
  "annemariewildeisen.ch": "bg-indigo-100 text-indigo-800",
}

function getDomainColor(domain: string | null): string {
  if (!domain) return "bg-gray-100 text-gray-600"
  return DOMAIN_COLORS[domain] || "bg-gray-100 text-gray-600"
}

export default function PublicPlanPage() {
  const { slug, year: yearParam, week: weekParam } = useParams<{
    slug: string
    year: string
    week: string
  }>()
  const [data, setData] = useState<PublicPlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const kwMatch = weekParam?.match(/^kw(\d+)$/i)

  useEffect(() => {
    if (!slug || !yearParam || !kwMatch) return

    const year = parseInt(yearParam)
    const week = parseInt(kwMatch[1])

    let cancelled = false

    fetch(`/api/public/plan/${slug}/${year}/${week}`, {
      headers: { "Content-Type": "application/json" },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Not found")
        return res.json()
      })
      .then((result) => {
        if (!cancelled) {
          setData(result)
          setError("")
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Dieser Plan ist nicht vorhanden oder nicht oeffentlich.")
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [slug, yearParam, weekParam, kwMatch])

  if (!slug || !yearParam || !kwMatch) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center space-y-2 p-4">
          <h1 className="text-6xl font-bold text-muted-foreground/30">404</h1>
          <p className="text-muted-foreground">Ungueltige URL</p>
        </div>
      </div>
    )
  }

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
        <div className="text-center space-y-2 p-4">
          <h1 className="text-6xl font-bold text-muted-foreground/30">404</h1>
          <p className="text-muted-foreground">
            {error || "Nicht gefunden"}
          </p>
        </div>
      </div>
    )
  }

  const getSlot = (day: number, meal: string): PublicSlot | undefined => {
    return data.slots.find(
      (s) => s.day_of_week === day && s.meal_type === meal
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-4 max-w-4xl mx-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">{data.household_name}</h1>
        <p className="text-lg text-muted-foreground">
          {formatWeekLabel(data.year, data.iso_week)}
        </p>
      </header>

      <div className="grid grid-cols-8 gap-1 text-sm">
        <div className="font-medium text-muted-foreground p-1" />
        {DAY_LABELS.map((day) => (
          <div
            key={day}
            className="text-center font-medium text-muted-foreground p-1"
          >
            {day}
          </div>
        ))}

        {MEAL_TYPES.map((meal) =>
          DAY_LABELS.map((_, dayIdx) => {
            const slot = getSlot(dayIdx, meal)
            const isActive = slot?.active !== false
            const recipe = slot?.recipe || null

            return (
              <div key={`${meal}-${dayIdx}`} className="contents">
                {dayIdx === 0 && (
                  <div className="text-sm font-medium p-1 flex items-center">
                    {MEAL_LABELS[meal]}
                  </div>
                )}
                <div
                  className={
                    `rounded border p-1 min-h-[90px] text-xs ${
                      isActive && recipe
                        ? "bg-background border-border"
                        : "bg-muted/30 text-muted-foreground/50 border-border/50"
                    }`
                  }
                >
                  {recipe ? (
                    <div className="flex flex-col items-center gap-1 h-full justify-center">
                      {slot?.cooked && (
                        <span className="text-green-600 text-xs font-bold">
                          Gekocht
                        </span>
                      )}
                      <span className="font-medium truncate w-full text-center">
                        {recipe.title}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {slot?.portions} Port.
                      </span>
                      {recipe.source_domain && (
                        <span
                          className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${getDomainColor(recipe.source_domain)}`}
                        >
                          {recipe.source_domain}
                        </span>
                      )}
                      {recipe.source_url && (
                        <a
                          href={recipe.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-primary hover:underline mt-0.5"
                        >
                          Originalrezept &rarr;
                        </a>
                      )}
                    </div>
                  ) : isActive ? (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      &mdash;
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full text-muted-foreground/40">
                      &mdash;
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      <footer className="mt-10 text-center">
        <p className="text-xs text-muted-foreground">
          Erstellt mit Chuchiplaner
        </p>
      </footer>
    </div>
  )
}
