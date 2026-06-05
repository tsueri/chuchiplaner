import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"

import { PageHeaderProvider } from "@/components/PageHeaderContext"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import WeekPlanPage from "./WeekPlanPage"

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

function renderPage({
  recipeSearchResponse,
}: {
  recipeSearchResponse?: unknown
} = {}) {
  const authValue: AuthContextType = {
    user: {
      id: 1,
      username: "alice",
      role: "admin",
      household_id: 1,
    },
    loading: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  }

  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url =
      typeof input === "string" ? input : (input as Request).url
    const method = (init?.method ?? "GET").toUpperCase()

    if (url === "/api/auth/me") {
      return Promise.resolve(jsonResponse(authValue.user))
    }

    // week data (GET /api/weeks/...)
    if (method === "GET" && url.startsWith("/api/weeks/")) {
      return Promise.resolve(
        jsonResponse({
          id: 1,
          household_id: 1,
          year: 2026,
          iso_week: 23,
          is_public: false,
          slots: [
            {
              id: 1,
              week_plan_id: 1,
              meal_type: "lunch",
              day_of_week: 0,
              active: true,
              recipe_id: null,
              recipe_title: null,
              portions: 4,
              dietary_filter_tag_id: null,
              cooked: false,
              planned_recipes: [],
            },
          ],
        })
      )
    }

    // POST /api/match
    if (method === "POST" && url === "/api/match") {
      return Promise.resolve(jsonResponse({ suggestions: [] }))
    }

    // GET /api/inventory
    if (method === "GET" && url === "/api/inventory?category=cooked") {
      return Promise.resolve(jsonResponse([]))
    }

    // GET /api/household
    if (url === "/api/household") {
      return Promise.resolve(jsonResponse({ slug: "test-hh" }))
    }

    // GET /api/recipes?search=...
    if (method === "GET" && url.startsWith("/api/recipes?")) {
      return Promise.resolve(
        jsonResponse(
          recipeSearchResponse ?? [
            {
              id: 39,
              title: "Himbeer-Glace-Creme mit Mug-Cakes",
              ingredients: [
                {
                  id: 358,
                  ingredient_id: 209,
                  quantity: 3,
                  unit: "EL",
                  order_index: 0,
                  ingredient_name: "Milch",
                },
              ],
            },
          ]
        )
      )
    }

    // PUT /api/weeks/.../slots
    if (method === "PUT" && url.includes("/slots")) {
      return Promise.resolve(jsonResponse({ status: "ok" }))
    }

    return Promise.resolve(jsonResponse({}))
  })

  const view = render(
    <AuthContext.Provider value={authValue}>
      <PageHeaderProvider>
        <MemoryRouter initialEntries={["/plan"]}>
          <WeekPlanPage />
        </MemoryRouter>
      </PageHeaderProvider>
    </AuthContext.Provider>
  )
  return view
}

describe("WeekPlanPage recipe search", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("maps recipe search id to recipe_id so drag-and-drop sets correct recipe ID", async () => {
    renderPage()

    const user = userEvent.setup()

    // Wait for the planner to load (PageHeader won't render the title
    // directly — it stores it in AppLayout context — so wait for the
    // sidebar's shell text instead)
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Menü suchen...")).toBeInTheDocument()
    })

    // Type a search query
    const searchInput = screen.getByPlaceholderText("Menü suchen...")
    await user.type(searchInput, "himbeer")

    // Wait for search results to appear
    await waitFor(() => {
      expect(
        screen.getByText("Himbeer-Glace-Creme mit Mug-Cakes")
      ).toBeInTheDocument()
    })

    // Find the search result element (it should be draggable)
    const searchResult = screen.getByText(
      "Himbeer-Glace-Creme mit Mug-Cakes"
    ).closest('[draggable="true"]')
    expect(searchResult).not.toBeNull()

    // Simulate dragstart and capture the dataTransfer data
    const dataTransfer: Record<string, string> = {}
    const dragStartEvent = new Event("dragstart", { bubbles: true }) as DragEvent
    Object.defineProperty(dragStartEvent, "dataTransfer", {
      value: {
        setData: (format: string, data: string) => {
          dataTransfer[format] = data
        },
        getData: (format: string) => dataTransfer[format] || "",
        effectAllowed: "",
      },
    })
    searchResult!.dispatchEvent(dragStartEvent)

    // The recipe_id in dataTransfer must be a valid number, not "undefined"
    const dragRecipeId = dataTransfer["recipe_id"]
    expect(dragRecipeId).toBeDefined()
    expect(dragRecipeId).toBe("39")
  })
})
