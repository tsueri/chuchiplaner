export const INGREDIENT_UNITS = [
  "g",
  "kg",
  "ml",
  "dl",
  "l",
  "EL",
  "TL",
  "Stück",
  "Bund",
  "Prise",
  "Msp",
] as const

export interface EditableIngredientValue {
  key: string
  ingredientId: number | null
  ingredientName: string
  query: string
  quantity: string
  unit: string
  suggestedIngredientId: number | null
  confidence: number
  raw: string
}

let rowKeyCounter = 0

export function defaultEditableIngredientValue(): EditableIngredientValue {
  rowKeyCounter += 1
  return {
    key: `row-${rowKeyCounter}`,
    ingredientId: null,
    ingredientName: "",
    query: "",
    quantity: "",
    unit: "g",
    suggestedIngredientId: null,
    confidence: 0,
    raw: "",
  }
}
