import { useCallback, useEffect, useState } from "react"
import { useAuth } from "@/contexts/AuthContext"
import { Button } from "@/components/ui/button"

interface Member {
  id: number
  username: string
  role: string
}

interface Household {
  id: number
  name: string
  slug: string
  invite_code: string
  default_size: number
  default_public: boolean
  members: Member[]
}

interface MealSlot {
  id: number
  household_id: number
  day_of_week: number
  meal_type: string
  active: boolean
  default_portions: number
}

interface SlotUpdate {
  day_of_week: number
  meal_type: string
  active?: boolean
  default_portions?: number
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

export default function SettingsPage() {
  const { user } = useAuth()
  const [household, setHousehold] = useState<Household | null>(null)
  const [slots, setSlots] = useState<MealSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [copied, setCopied] = useState(false)
  const [householdSize, setHouseholdSize] = useState(1)
  const [slotChanges, setSlotChanges] = useState<Map<string, SlotUpdate>>(new Map())
  const [slotSaving, setSlotSaving] = useState(false)
  const [sizeSaving, setSizeSaving] = useState(false)

  const slotKey = (day: number, meal: string) => `${day}-${meal}`

  const refreshAll = useCallback(() => {
    let cancelled = false
    Promise.all([api("/household"), api("/household/meal-template")])
      .then(([hData, sData]) => {
        if (!cancelled) {
          setHousehold(hData as Household)
          setHouseholdSize((hData as Household).default_size)
          setSlots(sData as MealSlot[])
          setSlotChanges(new Map())
          setError("")
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "Failed to load settings")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const cancel = refreshAll()
    return cancel
  }, [refreshAll])

  const copyInviteCode = async () => {
    if (!household) return
    await navigator.clipboard.writeText(
      `${window.location.origin}/register?invite_code=${household.invite_code}`
    )
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const regenerateCode = async () => {
    try {
      const data = await api("/household/invite-code", { method: "POST" })
      setHousehold((prev) => prev ? { ...prev, invite_code: data.invite_code } : null)
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to regenerate code")
    }
  }

  const removeMember = async (memberId: number) => {
    try {
      await api(`/household/members/${memberId}`, { method: "DELETE" })
      refreshAll()
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove member")
    }
  }

  const toggleSlot = (day: number, meal: string, current: boolean) => {
    const key = slotKey(day, meal)
    const next = new Map(slotChanges)
    const existing = next.get(key) || { day_of_week: day, meal_type: meal }
    next.set(key, { ...existing, active: !current })
    setSlotChanges(next)
  }

  const setSlotPortions = (day: number, meal: string, portions: number) => {
    const key = slotKey(day, meal)
    const next = new Map(slotChanges)
    const existing = next.get(key) || { day_of_week: day, meal_type: meal }
    next.set(key, { ...existing, default_portions: portions })
    setSlotChanges(next)
  }

  const getSlot = (day: number, meal: string): { active: boolean; portions: number } => {
    const base = slots.find(
      (s) => s.day_of_week === day && s.meal_type === meal
    )
    const change = slotChanges.get(slotKey(day, meal))
    return {
      active: change?.active ?? base?.active ?? true,
      portions: change?.default_portions ?? base?.default_portions ?? householdSize,
    }
  }

  const saveSlots = async () => {
    if (slotChanges.size === 0) return
    setSlotSaving(true)
    try {
      const updateList = Array.from(slotChanges.values()).map((c) => {
        const base = slots.find(
          (s) => s.day_of_week === c.day_of_week && s.meal_type === c.meal_type
        )
        const result: SlotUpdate = { day_of_week: c.day_of_week, meal_type: c.meal_type }
        if (c.active !== undefined) result.active = c.active
        if (c.default_portions !== undefined && c.default_portions !== (base?.default_portions ?? householdSize)) {
          result.default_portions = c.default_portions
        }
        return result
      }).filter((u) => u.active !== undefined || u.default_portions !== undefined)

      if (updateList.length > 0) {
        await api("/household/meal-template", {
          method: "PUT",
          body: JSON.stringify({ slots: updateList }),
        })
      }
      setSlotChanges(new Map())
      await refreshAll()
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save meal template")
    } finally {
      setSlotSaving(false)
    }
  }

  const saveHouseholdSize = async () => {
    setSizeSaving(true)
    try {
      await api("/household", {
        method: "PUT",
        body: JSON.stringify({ default_size: householdSize }),
      })
      await refreshAll()
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save household size")
    } finally {
      setSizeSaving(false)
    }
  }

  const toggleDefaultPublic = async () => {
    if (!household) return
    const next = !household.default_public
    try {
      await api("/household", {
        method: "PUT",
        body: JSON.stringify({ default_public: next }),
      })
      setHousehold({ ...household, default_public: next })
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save visibility setting")
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Laden...</p>
      </div>
    )
  }

  if (!household) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-destructive">{error || "Kein Haushalt gefunden"}</p>
      </div>
    )
  }

  const hasSlotChanges = slotChanges.size > 0
  const isAdmin = user?.role === "admin"

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <h1 className="text-2xl font-bold">Einstellungen</h1>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-4 rounded-lg border p-4">
        <h2 className="text-lg font-semibold">Haushalt</h2>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <span className="text-muted-foreground">Name:</span>
          <span>{household.name}</span>
          <span className="text-muted-foreground">Slug:</span>
          <span className="font-mono">{household.slug}</span>
          <span className="text-muted-foreground">Grösse:</span>
          <span>{household.default_size} Personen</span>
        </div>
      </div>

      {isAdmin && (
        <div className="space-y-4 rounded-lg border p-4">
          <h2 className="text-lg font-semibold">Haushaltsgrösse</h2>
          <div className="flex items-center gap-3">
            <input
              type="number"
              min={1}
              value={householdSize}
              onChange={(e) => setHouseholdSize(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-20 rounded border px-3 py-2 text-sm"
            />
            <span className="text-sm text-muted-foreground">Personen</span>
            <Button
              variant="outline"
              size="sm"
              onClick={saveHouseholdSize}
              disabled={sizeSaving || householdSize === household.default_size}
            >
              {sizeSaving ? "..." : "Speichern"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Ändert die Standardportionen aller Mahlzeiten auf diesen Wert.
          </p>
        </div>
      )}

      {isAdmin && (
        <div className="space-y-4 rounded-lg border p-4">
          <h2 className="text-lg font-semibold">Sichtbarkeit</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">
                Neue Wochen standardmaessig oeffentlich
              </p>
              <p className="text-xs text-muted-foreground">
                Wenn aktiv, werden neu erstellte Wochenplaene fuer jeden mit dem Link sichtbar.
              </p>
            </div>
            <button
              onClick={toggleDefaultPublic}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                household?.default_public ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  household?.default_public ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>
      )}

      {isAdmin && (
        <div className="space-y-4 rounded-lg border p-4 overflow-x-auto">
          <h2 className="text-lg font-semibold">Mahlzeiten</h2>

          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left p-1"></th>
                {DAY_LABELS.map((day) => (
                  <th key={day} className="p-1 text-center font-medium">
                    {day}
                  </th>
                ))}
                <th className="p-1 text-center font-medium">Port.</th>
              </tr>
            </thead>
            <tbody>
              {MEAL_TYPES.map((meal) => {
                const rowPortions = getSlot(0, meal).portions
                return (
                  <tr key={meal} className="border-t">
                    <td className="p-1 font-medium whitespace-nowrap">
                      {MEAL_LABELS[meal]}
                    </td>
                    {DAY_LABELS.map((_, dayIdx) => {
                      const slot = getSlot(dayIdx, meal)
                      return (
                        <td key={dayIdx} className="p-1 text-center">
                          <input
                            type="checkbox"
                            checked={slot.active}
                            onChange={() => toggleSlot(dayIdx, meal, slot.active)}
                            className="h-4 w-4"
                          />
                        </td>
                      )
                    })}
                    <td className="p-1 text-center">
                      <input
                        type="number"
                        min={1}
                        value={rowPortions}
                        onChange={(e) => {
                          const val = Math.max(1, parseInt(e.target.value) || 1)
                          DAY_LABELS.forEach((_, dayIdx) =>
                            setSlotPortions(dayIdx, meal, val)
                          )
                        }}
                        className="w-14 rounded border px-2 py-1 text-sm text-center"
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {hasSlotChanges && (
            <div className="flex justify-end">
              <Button onClick={saveSlots} disabled={slotSaving}>
                {slotSaving ? "Speichern..." : "Änderungen speichern"}
              </Button>
            </div>
          )}
        </div>
      )}

      {isAdmin && (
        <div className="space-y-4 rounded-lg border p-4">
          <h2 className="text-lg font-semibold">Einladungscode</h2>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-muted px-3 py-2 text-sm font-mono">
              {household.invite_code}
            </code>
            <Button variant="outline" size="sm" onClick={copyInviteCode}>
              {copied ? "Kopiert!" : "Link kopieren"}
            </Button>
            <Button variant="outline" size="sm" onClick={regenerateCode}>
              Neu generieren
            </Button>
          </div>
        </div>
      )}

      <div className="space-y-4 rounded-lg border p-4">
        <h2 className="text-lg font-semibold">
          Mitglieder ({household.members.length})
        </h2>
        <ul className="divide-y">
          {household.members.map((member) => (
            <li
              key={member.id}
              className="flex items-center justify-between py-2"
            >
              <div>
                <span className="font-medium">{member.username}</span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {member.role === "admin" ? "Admin" : "Mitglied"}
                </span>
              </div>
              {isAdmin && member.id !== user?.id && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => removeMember(member.id)}
                >
                  Entfernen
                </Button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
