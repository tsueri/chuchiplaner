import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { PageHeaderProvider } from "@/components/PageHeaderContext"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import CookModePage from "./CookModePage"

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

const recipeFixture = {
  id: 1,
  title: "Pfannkuchen",
  description: "Leckere Pfannkuchen",
  image_url: null,
  servings: 4,
  ingredients: [
    { id: 1, ingredient_id: 10, ingredient_name: "Mehl", quantity: 200, unit: "g", order_index: 0 },
    { id: 2, ingredient_id: 20, ingredient_name: "Milch", quantity: 300, unit: "ml", order_index: 1 },
  ],
  steps: [
    { id: 1, position: 0, text: "Mehl und Milch mischen.", name: "Teig" },
    { id: 2, position: 1, text: "In der Pfanne backen.", name: null },
  ],
}

const inventoryFixture = [
  { id: 1, household_id: 1, ingredient_id: 10, ingredient_name: "Mehl", quantity: 500, unit: "g", category: "raw", expiry_date: null },
  { id: 2, household_id: 1, ingredient_id: 20, ingredient_name: "Milch", quantity: 1000, unit: "ml", category: "raw", expiry_date: null },
]

const authValue: AuthContextType = {
  user: { id: 1, username: "alice", role: "admin", household_id: 1 },
  loading: false,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
}

function renderCook(
  recipe: unknown = recipeFixture,
  inventory: unknown = inventoryFixture,
  params = "/recipes/1/cook?portions=2",
) {
  const mockFetch = vi.fn((input: string | Request) => {
    const url = typeof input === "string" ? input : (input as Request).url
    if (url === "/api/recipes/1") return Promise.resolve(jsonResponse(recipe))
    if (url === "/api/inventory" || url.startsWith("/api/inventory?")) return Promise.resolve(jsonResponse(inventory))
    if (url.startsWith("/api/recipes/1/cook")) return Promise.resolve(jsonResponse({ cooked: true, deductions: [{ ingredient_id: 10, ingredient_name: "Mehl", deducted: 100, unit: "g" }] }))
    if (url.startsWith("/api/recipes/1/leftovers")) return Promise.resolve(jsonResponse({ id: 99, ingredient_name: "Pfannkuchen (Reste)", quantity: 2, unit: "St\u00fcck", category: "cooked", source_recipe_id: 1 }))
    return Promise.resolve(jsonResponse({}))
  })
  vi.stubGlobal("fetch", mockFetch)

  return {
    ...render(
      <AuthContext.Provider value={authValue}>
        <PageHeaderProvider>
          <MemoryRouter initialEntries={[params]}>
            <Routes>
              <Route path="/recipes/:id/cook" element={<CookModePage />} />
            </Routes>
          </MemoryRouter>
        </PageHeaderProvider>
      </AuthContext.Provider>,
    ),
    mockFetch,
  }
}

describe("CookModePage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it("renders recipe title, ingredients, and steps", async () => {
    renderCook()
    expect(await screen.findByText("Pfannkuchen")).toBeDefined()
    expect(screen.getByText("Leckere Pfannkuchen")).toBeDefined()
    expect(screen.getAllByText(/Mehl/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText(/Milch/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText("In der Pfanne backen.")).toBeDefined()
  })

  it("shows scaled ingredient quantities based on portions", async () => {
    renderCook(recipeFixture, inventoryFixture, "/recipes/1/cook?portions=2")
    expect(await screen.findByText(/100 g Mehl/)).toBeDefined()
    expect(screen.getByText(/150 ml Milch/)).toBeDefined()
  })

  it("shows inventory availability per ingredient", async () => {
    renderCook()
    expect(await screen.findByText(/im Vorrat: 500 g/)).toBeDefined()
    expect(screen.getByText(/im Vorrat: 1000 ml/)).toBeDefined()
  })

  it("has checkboxes for each ingredient", async () => {
    renderCook()
    const checkboxes = await screen.findAllByRole("checkbox")
    expect(checkboxes.length).toBe(2)
  })

  it("has a Gekocht button that opens leftovers modal", async () => {
    const user = userEvent.setup()
    renderCook()

    const gekochtBtn = await screen.findByRole("button", { name: "Gekocht" })
    await user.click(gekochtBtn)

    expect(await screen.findByText("Wie viele Portionen sind übrig?")).toBeDefined()
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDefined()
    expect(screen.getByRole("button", { name: "\u00dcberspringen" })).toBeDefined()
  })

  it("closes leftovers modal on skip", async () => {
    const user = userEvent.setup()
    renderCook()

    await user.click(await screen.findByRole("button", { name: "Gekocht" }))
    await user.click(await screen.findByRole("button", { name: "\u00dcberspringen" }))

    expect(screen.queryByText("Wie viele Portionen sind \u00fcbrig?")).toBeNull()
  })
})
