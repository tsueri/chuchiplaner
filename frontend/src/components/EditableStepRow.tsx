import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { X } from "lucide-react"
import type { EditableStepValue } from "./EditableStepRow.types"

export interface EditableStepRowProps {
  value: EditableStepValue
  onChange: (next: EditableStepValue) => void
  onRemove: () => void
  showNameInput: boolean
}

export function EditableStepRow({
  value,
  onChange,
  onRemove,
  showNameInput,
}: EditableStepRowProps) {
  return (
    <div className="flex items-start gap-2">
      <div className="flex-1 flex flex-col gap-1">
        {showNameInput && (
          <Input
            type="text"
            value={value.name}
            placeholder="Schrittname (optional)"
            aria-label="Schrittname"
            className="w-full"
            onChange={(e) => onChange({ ...value, name: e.target.value })}
          />
        )}
        <textarea
          value={value.text}
          placeholder="Schrittbeschreibung..."
          aria-label="Schritt"
          rows={2}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Schritt entfernen"
        onClick={onRemove}
      >
        <X />
      </Button>
    </div>
  )
}
