import { describe, it, expect, beforeEach, vi } from "vitest"
import { useState } from "react"
import { render, screen, cleanup } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { NutritionEditor, parseNutrition, nutritionFromApi } from "./NutritionEditor"
import { NUTRITION_FIELDS } from "./NutritionEditor.types"

function ControlledNutritionEditor({
  initial = {},
}: {
  initial?: Record<string, string>
}) {
  const [nutrition, setNutrition] = useState(initial)
  return (
    <NutritionEditor nutrition={nutrition} onChange={setNutrition} />
  )
}

describe("NutritionEditor", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders all 12 inputs", () => {
    render(<ControlledNutritionEditor />)

    for (const field of NUTRITION_FIELDS) {
      expect(screen.getByLabelText(field.label)).toBeInTheDocument()
    }
  })

  it("renders the Nährwerte heading", () => {
    render(<ControlledNutritionEditor />)

    expect(
      screen.getByRole("heading", { name: /nährwerte/i })
    ).toBeInTheDocument()
  })

  it("pre-fills values from the nutrition prop", () => {
    render(
      <ControlledNutritionEditor
        initial={{ calories: "240", proteinContent: "15" }}
      />
    )

    const caloriesInput = screen.getByLabelText("Kalorien") as HTMLInputElement
    expect(caloriesInput.value).toBe("240")

    const proteinInput = screen.getByLabelText("Protein") as HTMLInputElement
    expect(proteinInput.value).toBe("15")

    const carbsInput = screen.getByLabelText("Kohlenhydrate") as HTMLInputElement
    expect(carbsInput.value).toBe("")
  })

  it("updates value when typing", async () => {
    const user = userEvent.setup()
    render(<ControlledNutritionEditor />)

    const input = screen.getByLabelText("Kalorien")
    await user.type(input, "240")

    expect((input as HTMLInputElement).value).toBe("240")
  })

  it("removes the value when input is cleared", async () => {
    const user = userEvent.setup()
    render(
      <ControlledNutritionEditor initial={{ calories: "240" }} />
    )

    const input = screen.getByLabelText("Kalorien")
    expect((input as HTMLInputElement).value).toBe("240")

    await user.clear(input)

    expect((input as HTMLInputElement).value).toBe("")
  })

  it("accepts comma as decimal separator", async () => {
    const user = userEvent.setup()
    render(<ControlledNutritionEditor />)

    await user.type(screen.getByLabelText("Kohlenhydrate"), "30,5")

    expect(
      (screen.getByLabelText("Kohlenhydrate") as HTMLInputElement).value
    ).toBe("30,5")
  })

  it("shows the unit suffix next to each input", () => {
    render(<ControlledNutritionEditor />)

    expect(screen.getByText("kcal")).toBeInTheDocument()
    expect(screen.getAllByText("g").length).toBeGreaterThan(0)
    expect(screen.getAllByText("mg").length).toBeGreaterThan(0)
  })
})

describe("parseNutrition", () => {
  it("parses numeric strings to numbers", () => {
    expect(parseNutrition({ calories: "240", proteinContent: "15" })).toEqual({
      calories: 240,
      proteinContent: 15,
    })
  })

  it("parses comma as decimal separator", () => {
    expect(parseNutrition({ carbohydrateContent: "30,5" })).toEqual({
      carbohydrateContent: 30.5,
    })
  })

  it("skips empty strings", () => {
    expect(parseNutrition({ calories: "240", proteinContent: "" })).toEqual({
      calories: 240,
    })
  })

  it("skips non-numeric strings", () => {
    expect(parseNutrition({ calories: "abc" })).toEqual({})
  })

  it("returns empty object for empty input", () => {
    expect(parseNutrition({})).toEqual({})
  })
})

describe("nutritionFromApi", () => {
  it("returns empty object for null", () => {
    expect(nutritionFromApi(null)).toEqual({})
  })

  it("returns empty object for undefined", () => {
    expect(nutritionFromApi(undefined)).toEqual({})
  })

  it("converts numbers to strings", () => {
    expect(nutritionFromApi({ calories: 240, proteinContent: 15 })).toEqual({
      calories: "240",
      proteinContent: "15",
    })
  })

  it("handles nested value/unit format from NutritionParser", () => {
    expect(
      nutritionFromApi({
        calories: { value: 240, unit: "kcal" },
        carbohydrateContent: { value: 30.5, unit: "g" },
      })
    ).toEqual({
      calories: "240",
      carbohydrateContent: "30.5",
    })
  })

  it("skips unknown shapes", () => {
    expect(nutritionFromApi({ bogus: null })).toEqual({})
  })
})
