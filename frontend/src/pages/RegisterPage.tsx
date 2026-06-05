import { useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useAuth } from "@/contexts/useAuth"
import { Button } from "@/components/ui/button"

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [inviteCode, setInviteCode] = useState(searchParams.get("invite_code") || "")
  const [adminSignupCode, setAdminSignupCode] = useState(searchParams.get("admin_signup_code") || "")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError("")
    setSubmitting(true)
    try {
      await register(username, password, inviteCode || undefined, adminSignupCode || undefined)
      navigate("/")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border p-6"
      >
        <h1 className="text-2xl font-bold">Registrieren</h1>

        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="space-y-2">
          <label
            htmlFor="username"
            className="text-sm font-medium"
          >
            Benutzername
          </label>
          <input
            id="username"
            type="text"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="inviteCode"
            className="text-sm font-medium"
          >
            Einladungscode (optional)
          </label>
          <input
            id="inviteCode"
            type="text"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder="Von Admin erhalten"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="adminSignupCode"
            className="text-sm font-medium"
          >
            Admin-Signup-Code (optional)
          </label>
          <input
            id="adminSignupCode"
            type="text"
            value={adminSignupCode}
            onChange={(e) => setAdminSignupCode(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder="Vom Betreiber erhalten"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="password"
            className="text-sm font-medium"
          >
            Passwort
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
          />
        </div>

        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? "Wird registriert..." : "Registrieren"}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          Bereits ein Konto?{" "}
          <Link
            to="/login"
            className="text-primary underline underline-offset-2"
          >
            Anmelden
          </Link>
        </p>
      </form>
    </div>
  )
}
