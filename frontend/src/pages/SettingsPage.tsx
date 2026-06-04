import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/contexts/useAuth"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/PageHeader"

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

interface FavoriteRecipe {
  id: number
  title: string
  image_url: string | null
  source_url: string | null
  source_domain: string | null
}

interface UserNote {
  id: number
  recipe_id: number
  text: string
  visibility: string
  recipe_title: string | null
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
  const [householdName, setHouseholdName] = useState("")
  const [householdSlug, setHouseholdSlug] = useState("")
  const [nameSaving, setNameSaving] = useState(false)
  const [pwCurrent, setPwCurrent] = useState("")
  const [pwNew, setPwNew] = useState("")
  const [pwConfirm, setPwConfirm] = useState("")
  const [pwSaving, setPwSaving] = useState(false)
  const [pwSuccess, setPwSuccess] = useState("")
  const [favorites, setFavorites] = useState<FavoriteRecipe[]>([])
  const [notes, setNotes] = useState<UserNote[]>([])
  const [exporting, setExporting] = useState(false)
  const navigate = useNavigate()

  const slotKey = (day: number, meal: string) => `${day}-${meal}`

  const refreshAll = useCallback(() => {
    let cancelled = false
    Promise.all([api("/household"), api("/household/meal-template")])
      .then(([hData, sData]) => {
        if (!cancelled) {
          setHousehold(hData as Household)
          setHouseholdSize((hData as Household).default_size)
          setHouseholdName((hData as Household).name)
          setHouseholdSlug((hData as Household).slug)
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

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api("/auth/user/favorites").catch(() => [] as FavoriteRecipe[]),
      api("/auth/user/notes").catch(() => [] as UserNote[]),
    ]).then(([favData, noteData]) => {
      if (!cancelled) {
        setFavorites(favData as FavoriteRecipe[])
        setNotes(noteData as UserNote[])
      }
    })
    return () => { cancelled = true }
  }, [])

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

  const saveHouseholdName = async () => {
    setNameSaving(true)
    try {
      const body: Record<string, string> = {}
      if (householdName !== household?.name) body.name = householdName
      if (householdSlug !== household?.slug) body.slug = householdSlug
      if (Object.keys(body).length > 0) {
        await api("/household", {
          method: "PUT",
          body: JSON.stringify(body),
        })
      }
      await refreshAll()
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save household name")
    } finally {
      setNameSaving(false)
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

  const changePassword = async () => {
    if (pwNew !== pwConfirm) {
      setError("Die neuen Passwörter stimmen nicht überein.")
      return
    }
    setPwSaving(true)
    setPwSuccess("")
    setError("")
    try {
      await api("/auth/password", {
        method: "PUT",
        body: JSON.stringify({ current_password: pwCurrent, new_password: pwNew }),
      })
      setPwSuccess("Passwort wurde geändert.")
      setPwCurrent("")
      setPwNew("")
      setPwConfirm("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password")
    } finally {
      setPwSaving(false)
    }
  }

  const exportData = async () => {
    setExporting(true)
    try {
      const res = await fetch("/api/household/export", {
        credentials: "same-origin",
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Export failed" }))
        throw new Error(data.detail || "Export failed")
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      const disposition = res.headers.get("content-disposition")
      const match = disposition?.match(/filename="?([^"]+)"?/)
      a.download = match?.[1] ?? "export.json"
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed")
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return (
      <div className="p-4 text-muted-foreground">Laden...</div>
    )
  }

  if (!household) {
    return (
      <div className="p-4 text-destructive">{error || "Kein Haushalt gefunden"}</div>
    )
  }

  const hasSlotChanges = slotChanges.size > 0
  const isAdmin = user?.role === "admin"

  return (
    <div className="space-y-8">
      <PageHeader title="Einstellungen" />

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-4 rounded-lg border p-4">
        <h2 className="text-lg font-semibold">Profil</h2>
        <div className="space-y-3">
          <div>
            <span className="text-sm text-muted-foreground">Benutzername: </span>
            <span className="text-sm font-medium">{user?.username}</span>
          </div>
          <div className="space-y-2 max-w-sm">
            <h3 className="text-sm font-medium">Passwort ändern</h3>
            <input
              type="password"
              placeholder="Aktuelles Passwort"
              value={pwCurrent}
              onChange={(e) => setPwCurrent(e.target.value)}
              className="w-full rounded border px-3 py-2 text-sm"
            />
            <input
              type="password"
              placeholder="Neues Passwort (min. 8 Zeichen)"
              value={pwNew}
              onChange={(e) => setPwNew(e.target.value)}
              className="w-full rounded border px-3 py-2 text-sm"
            />
            <input
              type="password"
              placeholder="Neues Passwort bestätigen"
              value={pwConfirm}
              onChange={(e) => setPwConfirm(e.target.value)}
              className="w-full rounded border px-3 py-2 text-sm"
            />
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={changePassword}
                disabled={pwSaving || !pwCurrent || !pwNew || !pwConfirm}
              >
                {pwSaving ? "..." : "Passwort ändern"}
              </Button>
              {pwSuccess && (
                <span className="text-sm text-green-600">{pwSuccess}</span>
              )}
            </div>
          </div>
        </div>
      </div>

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
          <h2 className="text-lg font-semibold">Name & Slug</h2>
          <div className="space-y-3 max-w-sm">
            <div>
              <label className="text-sm text-muted-foreground block mb-1">
                Name
              </label>
              <input
                type="text"
                value={householdName}
                onChange={(e) => setHouseholdName(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground block mb-1">
                Slug
              </label>
              <input
                type="text"
                value={householdSlug}
                onChange={(e) => setHouseholdSlug(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm font-mono"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={saveHouseholdName}
              disabled={
                nameSaving ||
                (householdName === household?.name &&
                  householdSlug === household?.slug)
              }
            >
              {nameSaving ? "..." : "Speichern"}
            </Button>
          </div>
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

      <div className="space-y-4 rounded-lg border p-4">
        <h2 className="text-lg font-semibold">Meine Daten</h2>

        <div>
          <h3 className="text-sm font-medium mb-2">
            Meine Favoriten ({favorites.length})
          </h3>
          {favorites.length === 0 ? (
            <p className="text-sm text-muted-foreground">Keine Favoriten.</p>
          ) : (
            <ul className="divide-y">
              {favorites.map((fav) => (
                <li key={fav.id} className="py-2">
                  <button
                    onClick={() => navigate(`/recipes/${fav.id}`)}
                    className="text-sm text-primary hover:underline text-left"
                  >
                    {fav.title}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3 className="text-sm font-medium mb-2">
            Meine Notizen ({notes.length})
          </h3>
          {notes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Keine Notizen.</p>
          ) : (
            <ul className="divide-y">
              {notes.map((note) => (
                <li key={note.id} className="py-2 space-y-1">
                  <button
                    onClick={() => navigate(`/recipes/${note.recipe_id}`)}
                    className="text-sm text-primary hover:underline text-left"
                  >
                    {note.recipe_title || `Rezept #${note.recipe_id}`}
                  </button>
                  <p className="text-sm text-muted-foreground">
                    {note.text.slice(0, 100)}{note.text.length > 100 ? "…" : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="space-y-4 rounded-lg border p-4">
        <h2 className="text-lg font-semibold">Datensicherung</h2>
        <p className="text-sm text-muted-foreground">
          Lade alle Daten deines Haushalts als JSON-Datei herunter. Kein
          Passwort-Hash im Export enthalten.
        </p>
        <Button variant="outline" onClick={exportData} disabled={exporting}>
          {exporting ? "Exportiere..." : "Daten exportieren"}
        </Button>
      </div>
    </div>
  )
}
