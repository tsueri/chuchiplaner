import { useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router-dom"

import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/PageHeader"

interface FormState {
  title: string
  instructions: string
  servings: number
  image_url: string
  source_url: string
  source_domain: string
}

const INITIAL_STATE: FormState = {
  title: "",
  instructions: "",
  servings: 4,
  image_url: "",
  source_url: "",
  source_domain: "",
}

async function postRecipe(
  body: {
    title: string
    instructions: string
    servings: number
    image_url: string | null
    source_url: string | null
    source_domain: string | null
    ingredients: []
  }
): Promise<{ id: number }> {
  const res = await fetch("/api/recipes", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Request failed" }))
    throw new Error(data.detail || "Request failed")
  }
  return res.json() as Promise<{ id: number }>
}

function toNull(value: string): string | null {
  return value.trim() === "" ? null : value
}

export default function RecipeFormPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState>(INITIAL_STATE)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const canSubmit =
    form.title.trim() !== "" && form.instructions.trim() !== "" && !submitting

  const handleSourceUrlBlur = () => {
    if (form.source_url.trim() === "") return
    if (form.source_domain.trim() !== "") return
    try {
      const hostname = new URL(form.source_url.trim()).hostname
      update("source_domain", hostname)
    } catch {
      // ignore invalid URL
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const created = await postRecipe({
        title: form.title.trim(),
        instructions: form.instructions.trim(),
        servings: form.servings,
        image_url: toNull(form.image_url),
        source_url: toNull(form.source_url),
        source_domain: toNull(form.source_domain),
        ingredients: [],
      })
      navigate(`/recipes/${created.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen")
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader title="Neues Rezept" />

      <form
        onSubmit={handleSubmit}
        className="mx-auto max-w-2xl space-y-4 rounded-lg border bg-card p-6"
      >
        {error && (
          <div
            role="alert"
            className="rounded-md bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="recipe-title" className="text-sm font-medium">
            Titel
          </label>
          <Input
            id="recipe-title"
            type="text"
            value={form.title}
            onChange={(e) => update("title", e.target.value)}
            required
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-instructions" className="text-sm font-medium">
            Zubereitung
          </label>
          <textarea
            id="recipe-instructions"
            value={form.instructions}
            onChange={(e) => update("instructions", e.target.value)}
            rows={6}
            required
            className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-servings" className="text-sm font-medium">
            Portionen
          </label>
          <Input
            id="recipe-servings"
            type="number"
            min={1}
            value={form.servings}
            onChange={(e) =>
              update("servings", Math.max(1, Number(e.target.value) || 1))
            }
            required
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-image-url" className="text-sm font-medium">
            Bild-URL
          </label>
          <Input
            id="recipe-image-url"
            type="url"
            value={form.image_url}
            onChange={(e) => update("image_url", e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-source-url" className="text-sm font-medium">
            Quelle
          </label>
          <Input
            id="recipe-source-url"
            type="url"
            value={form.source_url}
            onChange={(e) => update("source_url", e.target.value)}
            onBlur={handleSourceUrlBlur}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="recipe-source-domain" className="text-sm font-medium">
            Quell-Domain
          </label>
          <Input
            id="recipe-source-domain"
            type="text"
            value={form.source_domain}
            onChange={(e) => update("source_domain", e.target.value)}
          />
        </div>

        <div className="flex items-center justify-end gap-2 pt-2">
          <Link
            to="/recipes"
            className={buttonVariants({ variant: "ghost" })}
          >
            Abbrechen
          </Link>
          <Button type="submit" disabled={!canSubmit}>
            {submitting ? "Wird gespeichert..." : "Speichern"}
          </Button>
        </div>
      </form>
    </div>
  )
}
