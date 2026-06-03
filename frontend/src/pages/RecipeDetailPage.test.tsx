import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { PageHeaderProvider } from "@/components/PageHeaderContext"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import RecipeDetailPage from "./RecipeDetailPage"

function renderDetail(recipe: unknown) {
  const authValue: AuthContextType = {
    user: { id: 1, username: "alice", role: "admin", household_id: 1 },
    loading: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  }
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url =
      typeof input === "string" ? input : (input as Request).url
    if (url === "/api/recipes/1") {
      return Promise.resolve(
        new Response(JSON.stringify(recipe), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    }
    if (url === "/api/recipes/1/notes") {
      return Promise.resolve(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    }
    if (url === "/api/tags") {
      return Promise.resolve(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    }
    return Promise.resolve(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )
  })

  return render(
    <AuthContext.Provider value={authValue}>
      <PageHeaderProvider>
        <MemoryRouter initialEntries={["/recipes/1"]}>
          <Routes>
            <Route path="/recipes/:id" element={<RecipeDetailPage />} />
          </Routes>
        </MemoryRouter>
      </PageHeaderProvider>
    </AuthContext.Provider>
  )
}

const baseRecipe = {
  id: 1,
  title: "Pouletgeschnetzeltes",
  instructions: "Alles anbraten.",
  image_url: null,
  source_url: null,
  source_domain: null,
  servings: 4,
  household_id: 1,
  tags: [],
  is_favorited: false,
  created_at: null,
}

describe("RecipeDetailPage ingredient rendering", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders each ingredient row as '{quantity} {unit} {ingredient_name}' in order_index order", async () => {
    renderDetail({
      ...baseRecipe,
      ingredients: [
        {
          id: 10,
          ingredient_id: 100,
          quantity: 600,
          unit: "g",
          ingredient_name: "Pouletbrust",
          order_index: 0,
        },
        {
          id: 11,
          ingredient_id: 101,
          quantity: 1,
          unit: "Stück",
          ingredient_name: "Zwiebel",
          order_index: 1,
        },
      ],
    })

    expect(
      await screen.findByText("600 g Pouletbrust")
    ).toBeInTheDocument()
    expect(screen.getByText("1 Stück Zwiebel")).toBeInTheDocument()
  })

  it("hides the Zutaten section when the recipe has zero ingredients", async () => {
    renderDetail({
      ...baseRecipe,
      ingredients: [],
    })

    expect(
      await screen.findByRole("heading", { level: 1, name: "Pouletgeschnetzeltes" })
    ).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: /zutaten/i })).toBeNull()
  })
})
