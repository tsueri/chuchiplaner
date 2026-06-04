import { describe, it, expect, beforeEach, vi } from "vitest"
import { useState } from "react"
import { render, screen, cleanup } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { EditableStepRow } from "./EditableStepRow"
import {
  defaultEditableStepValue,
  type EditableStepValue,
} from "./EditableStepRow.types"

function ControlledRow({
  initial,
  showNameInput = false,
  onRemove,
}: {
  initial?: Partial<EditableStepValue>
  showNameInput?: boolean
  onRemove?: () => void
}) {
  const [value, setValue] = useState<EditableStepValue>({
    ...defaultEditableStepValue(),
    ...initial,
  })
  return (
    <EditableStepRow
      value={value}
      onChange={setValue}
      onRemove={onRemove ?? (() => {})}
      showNameInput={showNameInput}
    />
  )
}

describe("EditableStepRow", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders a text input and remove button for a fresh row", () => {
    render(<ControlledRow />)

    expect(screen.getByLabelText("Schritt")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /schritt entfernen/i })
    ).toBeInTheDocument()
  })

  it("does not render the name input when showNameInput is false", () => {
    render(<ControlledRow showNameInput={false} />)

    expect(screen.queryByLabelText("Schrittname")).not.toBeInTheDocument()
    expect(screen.getByLabelText("Schritt")).toBeInTheDocument()
  })

  it("renders the name input when showNameInput is true", () => {
    render(<ControlledRow showNameInput={true} />)

    expect(screen.getByLabelText("Schrittname")).toBeInTheDocument()
    expect(screen.getByLabelText("Schritt")).toBeInTheDocument()
  })

  it("populates the row from a prefilled value", () => {
    render(
      <ControlledRow
        initial={{
          key: "prefilled-1",
          name: "Teig zubereiten",
          text: "Mehl und Wasser mischen.",
        }}
        showNameInput={true}
      />
    )

    const nameInput = screen.getByLabelText("Schrittname") as HTMLInputElement
    const stepInput = screen.getByLabelText("Schritt") as HTMLTextAreaElement
    expect(nameInput.value).toBe("Teig zubereiten")
    expect(stepInput.value).toBe("Mehl und Wasser mischen.")
  })

  it("typing in the name input updates the rendered value", async () => {
    const user = userEvent.setup()
    render(<ControlledRow showNameInput={true} />)

    const nameInput = screen.getByLabelText("Schrittname")
    await user.type(nameInput, "Sauce")

    expect((nameInput as HTMLInputElement).value).toBe("Sauce")
  })

  it("typing in the step text input updates the rendered value", async () => {
    const user = userEvent.setup()
    render(<ControlledRow />)

    const stepInput = screen.getByLabelText("Schritt")
    await user.type(stepInput, "Alles mischen.")

    expect((stepInput as HTMLTextAreaElement).value).toBe("Alles mischen.")
  })

  it("clicking the remove button calls onRemove exactly once", async () => {
    const user = userEvent.setup()
    const onRemove = vi.fn()

    render(<ControlledRow onRemove={onRemove} />)

    await user.click(
      screen.getByRole("button", { name: /schritt entfernen/i })
    )

    expect(onRemove).toHaveBeenCalledTimes(1)
  })
})
