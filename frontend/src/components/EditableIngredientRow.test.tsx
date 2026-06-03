import { describe, it, expect, beforeEach, vi } from "vitest"
import { useState } from "react"
import { render, screen, cleanup, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { EditableIngredientRow } from "./EditableIngredientRow"
import {
  defaultEditableIngredientValue,
  type EditableIngredientValue,
} from "./EditableIngredientRow.types"

function mockFetchResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

function ControlledRow({
  initial,
  onRemove,
}: {
  initial?: Partial<EditableIngredientValue>
  onRemove?: () => void
}) {
  const [value, setValue] = useState<EditableIngredientValue>({
    ...defaultEditableIngredientValue(),
    ...initial,
  })
  return (
    <EditableIngredientRow
      value={value}
      onChange={setValue}
      onRemove={onRemove ?? (() => {})}
    />
  )
}

describe("EditableIngredientRow", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders a combobox, quantity input, unit select, and remove button for a fresh row", () => {
    render(<ControlledRow />)

    expect(screen.getByRole("combobox", { name: /zutat/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/menge/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/einheit/i)).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /zutat entfernen/i })
    ).toBeInTheDocument()
  })

  it("default quantity is empty string and default unit is 'g'", () => {
    render(<ControlledRow />)

    const quantity = screen.getByLabelText(/menge/i) as HTMLInputElement
    const unit = screen.getByLabelText(/einheit/i) as HTMLSelectElement

    expect(quantity.value).toBe("")
    expect(unit.value).toBe("g")
  })

  it("populates the row from a non-default value (edit-mode prefilled state)", () => {
    render(
      <ControlledRow
        initial={{
          key: "prefilled-1",
          ingredientId: 7,
          ingredientName: "Tomaten",
          quantity: "500",
          unit: "g",
          confidence: 1.0,
          raw: "500 g Tomaten",
        }}
      />
    )

    expect(screen.getByText("Tomaten")).toBeInTheDocument()
    expect(
      screen.queryByRole("combobox", { name: /zutat/i })
    ).not.toBeInTheDocument()

    const quantity = screen.getByLabelText(/menge/i) as HTMLInputElement
    const unit = screen.getByLabelText(/einheit/i) as HTMLSelectElement
    expect(quantity.value).toBe("500")
    expect(unit.value).toBe("g")
  })

  it("typing in the quantity input updates the rendered value", async () => {
    const user = userEvent.setup()
    render(<ControlledRow />)

    const quantity = screen.getByLabelText(/menge/i) as HTMLInputElement
    await user.type(quantity, "5")

    expect(quantity.value).toBe("5")
  })

  it("changing the unit updates the rendered value", async () => {
    const user = userEvent.setup()
    render(<ControlledRow />)

    const unit = screen.getByLabelText(/einheit/i) as HTMLSelectElement
    await user.selectOptions(unit, "Stück")

    expect(unit.value).toBe("Stück")
  })

  it("typing in the combobox debounces and queries /api/ingredients?q=…", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockFetchResponse([]))

    render(<ControlledRow />)

    const combobox = screen.getByRole("combobox", { name: /zutat/i })
    await user.type(combobox, "Tom")

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/api/ingredients?q=Tom"),
        expect.objectContaining({ credentials: "same-origin" })
      )
    })
  })

  it("clicking a result locks the row to that ingredient (name in place of input)", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/ingredients")) {
        return Promise.resolve(
          mockFetchResponse([{ id: 7, name: "Tomaten" }])
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    render(<ControlledRow />)

    const combobox = screen.getByRole("combobox", { name: /zutat/i })
    await user.type(combobox, "Tom")
    const option = await screen.findByRole("option", { name: /tomaten/i })
    await user.click(option)

    expect(screen.getByText("Tomaten")).toBeInTheDocument()
    expect(
      screen.queryByRole("combobox", { name: /zutat/i })
    ).not.toBeInTheDocument()
  })

  it("↻ override button on a locked chip unlocks the row and opens the catalog search with the ingredient name as query", async () => {
    const user = userEvent.setup()
    render(
      <ControlledRow
        initial={{
          key: "prefilled-1",
          ingredientId: 7,
          ingredientName: "Tomaten",
          quantity: "500",
          unit: "g",
          confidence: 1.0,
          raw: "500 g Tomaten",
        }}
      />
    )

    expect(screen.getByText("Tomaten")).toBeInTheDocument()
    expect(
      screen.queryByRole("combobox", { name: /zutat/i })
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /zutat ändern/i }))

    const combobox = screen.getByRole("combobox", { name: /zutat/i })
    expect((combobox as HTMLInputElement).value).toBe("Tomaten")
  })

  it("renders a fuzzy-match dropdown with highlighted suggestion and 'Anderer Vorschlag…' when suggestedIngredientId is set", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/ingredients")) {
        return Promise.resolve(
          mockFetchResponse([{ id: 8, name: "Zwiebeln" }])
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    render(
      <ControlledRow
        initial={{
          key: "fuzzy-1",
          query: "Zwiebel",
          quantity: "2",
          unit: "Stück",
          suggestedIngredientId: 8,
          confidence: 0.8,
          raw: "Zwiebel",
        }}
      />
    )

    const listbox = await screen.findByRole("listbox")
    const options = listbox.querySelectorAll('[role="option"]')
    const highlighted = Array.from(options).find(
      (o) => o.getAttribute("aria-selected") === "true"
    )
    expect(highlighted).toBeDefined()
    expect(highlighted).toHaveTextContent("Zwiebeln")
    expect(
      screen.getByRole("option", { name: /anderer vorschlag/i })
    ).toBeInTheDocument()
  })

  it("renders the raw text caption when the row carries a raw scraped string", () => {
    render(
      <ControlledRow
        initial={{
          key: "with-raw",
          query: "600g Kalbfleisch",
          quantity: "600",
          unit: "g",
          raw: "600g Kalbfleisch",
        }}
      />
    )

    expect(screen.getByText("600g Kalbfleisch")).toBeInTheDocument()
  })

  it("clicking the remove button calls onRemove exactly once", async () => {
    const user = userEvent.setup()
    const onRemove = vi.fn()

    render(<ControlledRow onRemove={onRemove} />)

    await user.click(
      screen.getByRole("button", { name: /zutat entfernen/i })
    )

    expect(onRemove).toHaveBeenCalledTimes(1)
  })
})
