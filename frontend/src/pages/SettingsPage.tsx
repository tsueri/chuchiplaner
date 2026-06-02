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
  members: Member[]
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
  return res.json()
}

export default function SettingsPage() {
  const { user } = useAuth()
  const [household, setHousehold] = useState<Household | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [copied, setCopied] = useState(false)

  const refreshHousehold = useCallback(() => {
    let cancelled = false
    api("/household")
      .then((data: Household) => {
        if (!cancelled) {
          setHousehold(data)
          setError("")
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "Failed to load household")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const cancel = refreshHousehold()
    return cancel
  }, [refreshHousehold])

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
      refreshHousehold()
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove member")
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
        </div>
      </div>

      {user?.role === "admin" && (
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
              {user?.role === "admin" && member.id !== user?.id && (
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
