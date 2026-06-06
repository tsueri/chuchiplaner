import { useEffect, useState } from "react"
import { X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import {
  INGREDIENT_UNITS,
  type EditableIngredientValue,
} from "./EditableIngredientRow.types"

const INGREDIENT_DEBOUNCE_MS = 200

interface Ingredient {
  id: number
  name: string
}

interface IngredientComboboxProps {
  value: EditableIngredientValue
  onChange: (next: EditableIngredientValue) => void
}

function IngredientCombobox({ value, onChange }: IngredientComboboxProps) {
  const [results, setResults] = useState<Ingredient[]>([])
  const [manuallyClosed, setManuallyClosed] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchCompleted, setSearchCompleted] = useState(false)
  const [userInteracted, setUserInteracted] = useState(false)
  const locked = value.ingredientId !== null

  const createIngredient = async (name: string) => {
    setCreating(true)
    try {
      const res = await fetch("/api/ingredients", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      })
      if (!res.ok) return
      const created = (await res.json()) as Ingredient
      onChange({
        ...value,
        ingredientId: created.id,
        ingredientName: created.name,
        query: "",
        suggestedIngredientId: null,
      })
    } finally {
      setCreating(false)
    }
  }

  useEffect(() => {
    if (locked) return
    const query = value.query.trim()
    if (query === "") return
    const controller = new AbortController()
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/ingredients?q=${encodeURIComponent(query)}`,
          {
            credentials: "same-origin",
            signal: controller.signal,
          }
        )
        if (!res.ok) return
        const data = (await res.json()) as Ingredient[]
        if (!controller.signal.aborted) {
          setResults(data)
          setSearchCompleted(true)
        }
      } catch {
        // aborted or network error — ignore
      }
    }, INGREDIENT_DEBOUNCE_MS)
    return () => {
      clearTimeout(t)
      controller.abort()
    }
  }, [value.query, locked])

  const queryTrimmed = value.query.trim()
  const showDropdown =
    !locked &&
    queryTrimmed !== "" &&
    !manuallyClosed &&
    (results.length > 0 || (searchCompleted && userInteracted))

  if (locked) {
    return (
      <div className="flex-1 flex flex-col gap-0.5">
        <div className="flex items-center gap-1">
          <span
            aria-label="Zutat"
            className="flex-1 truncate rounded-md border border-input bg-muted px-2.5 py-1 text-sm"
          >
            {value.ingredientName}
          </span>
          <button
            type="button"
            aria-label="Zutat ändern"
            className="inline-flex items-center justify-center rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground shrink-0"
            onClick={() => {
              onChange({
                ...value,
                ingredientId: null,
                ingredientName: "",
                query: value.ingredientName,
                suggestedIngredientId: null,
                confidence: 0,
              })
            }}
          >
            ↻
          </button>
        </div>
        {value.raw && (
          <span className="text-xs text-muted-foreground truncate">
            {value.raw}
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="relative flex-1 flex flex-col gap-0.5">
      <Input
        type="text"
        role="combobox"
        value={value.query}
        placeholder="Zutat suchen..."
        aria-label="Zutat"
        aria-autocomplete="list"
        aria-expanded={showDropdown}
        aria-controls={`ingredient-list-${value.key}`}
        className="w-full"
        onChange={(e) => {
          setResults([])
          setSearchCompleted(false)
          setManuallyClosed(false)
          onChange({ ...value, query: e.target.value, suggestedIngredientId: null })
        }}
        onFocus={() => { setManuallyClosed(false); setUserInteracted(true) }}
        onBlur={() => setManuallyClosed(true)}
      />
      {value.raw && (
        <span className="text-xs text-muted-foreground truncate">
          {value.raw}
        </span>
      )}
      {showDropdown && (
        <ul
          id={`ingredient-list-${value.key}`}
          role="listbox"
          className="absolute z-10 mt-1 max-h-40 w-full overflow-auto rounded-md border bg-popover shadow"
        >
          {results.map((ing) => (
            <li
              key={ing.id}
              role="option"
              aria-selected={ing.id === value.suggestedIngredientId}
              tabIndex={0}
              onMouseDown={(e) => {
                e.preventDefault()
                onChange({
                  ...value,
                  ingredientId: ing.id,
                  ingredientName: ing.name,
                  query: "",
                  suggestedIngredientId: null,
                })
              }}
              className={cn(
                "cursor-pointer px-2.5 py-1 text-sm hover:bg-muted",
                ing.id === value.suggestedIngredientId && "bg-muted font-medium"
              )}
            >
              {ing.name}
            </li>
          ))}
          {results.length === 0 && queryTrimmed !== "" && (
            <li
              role="option"
              tabIndex={0}
              onMouseDown={(e) => {
                e.preventDefault()
                createIngredient(queryTrimmed)
              }}
              className="cursor-pointer px-2.5 py-1 text-sm text-primary hover:bg-muted"
            >
              {creating ? "Erstelle..." : `"${queryTrimmed}" erstellen`}
            </li>
          )}
          {value.suggestedIngredientId !== null && (
            <li
              role="option"
              tabIndex={0}
              onMouseDown={(e) => {
                e.preventDefault()
                onChange({
                  ...value,
                  suggestedIngredientId: null,
                })
              }}
              className="cursor-pointer px-2.5 py-1 text-sm text-muted-foreground border-t hover:bg-muted"
            >
              Anderer Vorschlag…
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

export interface EditableIngredientRowProps {
  value: EditableIngredientValue
  onChange: (next: EditableIngredientValue) => void
  onRemove: () => void
}

export function EditableIngredientRow({
  value,
  onChange,
  onRemove,
}: EditableIngredientRowProps) {
  return (
    <div className="flex items-center gap-2">
      <IngredientCombobox value={value} onChange={onChange} />
      {value.suggestedIngredientName && !value.ingredientId && (
        <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
          Neu
        </span>
      )}
      <Input
        type="number"
        step="any"
        min="0"
        value={value.quantity}
        placeholder="Menge"
        aria-label="Menge"
        className="w-20"
        onChange={(e) => onChange({ ...value, quantity: e.target.value })}
      />
      <select
        aria-label="Einheit"
        value={value.unit}
        onChange={(e) => onChange({ ...value, unit: e.target.value })}
        className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
      >
        {INGREDIENT_UNITS.map((u) => (
          <option key={u} value={u}>
            {u}
          </option>
        ))}
      </select>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Zutat entfernen"
        onClick={onRemove}
      >
        <X />
      </Button>
    </div>
  )
}
