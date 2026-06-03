import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { PageHeaderProvider } from "@/components/PageHeaderContext"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import RecipeListPage from "./RecipeListPage"

function renderList() {
  const authValue: AuthContextType = {
    user: { id: 1, username: "alice", role: "admin", household_id: 1 },
    loading: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  }
  return render(
    <AuthContext.Provider value={authValue}>
      <PageHeaderProvider>
        <MemoryRouter initialEntries={["/recipes"]}>
          <Routes>
            <Route path="/recipes" element={<RecipeListPage />} />
            <Route
              path="/recipes/:id"
              element={<div>recipe-detail-stub</div>}
            />
          </Routes>
        </MemoryRouter>
      </PageHeaderProvider>
    </AuthContext.Provider>
  )
}

function mockFetchResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

const recipeA = {
  id: 1,
  title: "Pouletgeschnetzeltes",
  description: null,
  image_url: null,
  source_url: null,
  source_domain: null,
  servings: 4,
  prep_time_minutes: null,
  cook_time_minutes: null,
  total_time_minutes: null,
  perform_time_minutes: null,
  nutrition: null,
  aggregate_rating: null,
  keywords: null,
  author: null,
  date_published: null,
  household_id: 1,
  tags: [],
  is_favorited: false,
  created_at: null,
  steps: [],
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
}

const recipeB = {
  id: 2,
  title: "Pasta Pomodoro",
  description: null,
  image_url: null,
  source_url: null,
  source_domain: null,
  servings: 2,
  prep_time_minutes: null,
  cook_time_minutes: null,
  total_time_minutes: null,
  perform_time_minutes: null,
  nutrition: null,
  aggregate_rating: null,
  keywords: null,
  author: null,
  date_published: null,
  household_id: 1,
  tags: [],
  is_favorited: false,
  created_at: null,
  steps: [],
  ingredients: [
    {
      id: 20,
      ingredient_id: 200,
      quantity: 400,
      unit: "g",
      ingredient_name: "Spaghetti",
      order_index: 0,
    },
  ],
}

describe("RecipeListPage card expand", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("default state on page load is collapsed: no ingredient rows are visible", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/tags")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url.includes("/api/recipes")) {
        return Promise.resolve(mockFetchResponse([recipeA, recipeB]))
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderList()

    await screen.findByText("Pouletgeschnetzeltes")
    await screen.findByText("Pasta Pomodoro")

    // No ingredient text is rendered yet
    expect(screen.queryByText("600 g Pouletbrust")).not.toBeInTheDocument()
    expect(screen.queryByText("1 Stück Zwiebel")).not.toBeInTheDocument()
    expect(screen.queryByText("400 g Spaghetti")).not.toBeInTheDocument()
  })

  it("renders a 'Zutaten anzeigen' toggle button on each card, clearly separate from the title link", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/tags")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url.includes("/api/recipes")) {
        return Promise.resolve(mockFetchResponse([recipeA, recipeB]))
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderList()

    await screen.findByText("Pouletgeschnetzeltes")
    await screen.findByText("Pasta Pomodoro")

    const toggles = screen.getAllByRole("button", {
      name: /zutaten anzeigen/i,
    })
    expect(toggles).toHaveLength(2)

    // The title is still a link, not a button
    const titleLinks = screen.getAllByRole("link", {
      name: /pouletgeschnetzeltes|pasta pomodoro/i,
    })
    expect(titleLinks).toHaveLength(2)
  })

  it("clicking the toggle reveals the joined ingredients inline using '{quantity} {unit} {name}'", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/tags")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url.includes("/api/recipes")) {
        return Promise.resolve(mockFetchResponse([recipeA]))
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderList()

    await screen.findByText("Pouletgeschnetzeltes")

    await user.click(
      screen.getByRole("button", { name: /zutaten anzeigen/i })
    )

    expect(
      await screen.findByText("600 g Pouletbrust")
    ).toBeInTheDocument()
    expect(screen.getByText("1 Stück Zwiebel")).toBeInTheDocument()
  })

  it("clicking the same card's toggle again collapses it (no ingredient rows visible)", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/tags")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url.includes("/api/recipes")) {
        return Promise.resolve(mockFetchResponse([recipeA]))
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderList()

    await screen.findByText("Pouletgeschnetzeltes")

    const toggle = screen.getByRole("button", {
      name: /zutaten anzeigen/i,
    })
    await user.click(toggle)
    expect(
      await screen.findByText("600 g Pouletbrust")
    ).toBeInTheDocument()

    // The toggle label is now "Zutaten verbergen" while expanded
    await user.click(
      screen.getByRole("button", { name: /zutaten verbergen/i })
    )

    await waitFor(() => {
      expect(screen.queryByText("600 g Pouletbrust")).not.toBeInTheDocument()
    })
    expect(screen.queryByText("1 Stück Zwiebel")).not.toBeInTheDocument()
  })

  it("opening a different card collapses the previously open card (one-at-a-time)", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/tags")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url.includes("/api/recipes")) {
        return Promise.resolve(mockFetchResponse([recipeA, recipeB]))
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderList()

    await screen.findByText("Pouletgeschnetzeltes")
    await screen.findByText("Pasta Pomodoro")

    // Open card A
    const toggles = screen.getAllByRole("button", {
      name: /zutaten anzeigen/i,
    })
    await user.click(toggles[0])
    expect(
      await screen.findByText("600 g Pouletbrust")
    ).toBeInTheDocument()
    expect(screen.getByText("1 Stück Zwiebel")).toBeInTheDocument()

    // Now open card B — card A should collapse
    const remainingToggles = screen.getAllByRole("button", {
      name: /zutaten anzeigen/i,
    })
    expect(remainingToggles).toHaveLength(1)
    await user.click(remainingToggles[0])
    expect(
      await screen.findByText("400 g Spaghetti")
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.queryByText("600 g Pouletbrust")).not.toBeInTheDocument()
    })
    expect(screen.queryByText("1 Stück Zwiebel")).not.toBeInTheDocument()
  })

  it("the card's title link still navigates to /recipes/:id when clicked", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/tags")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url.includes("/api/recipes")) {
        return Promise.resolve(mockFetchResponse([recipeA]))
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderList()

    const titleLink = await screen.findByRole("link", {
      name: /pouletgeschnetzeltes/i,
    })
    expect(titleLink).toHaveAttribute("href", "/recipes/1")

    await user.click(titleLink)

    expect(
      await screen.findByText("recipe-detail-stub")
    ).toBeInTheDocument()
  })

  it("does NOT issue a second /api/recipes request when a card is expanded (single roundtrip)", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url.includes("/api/tags")) {
          return Promise.resolve(mockFetchResponse([]))
        }
        if (url.includes("/api/recipes")) {
          return Promise.resolve(mockFetchResponse([recipeA, recipeB]))
        }
        return Promise.resolve(mockFetchResponse([]))
      })

    renderList()

    await screen.findByText("Pouletgeschnetzeltes")
    await screen.findByText("Pasta Pomodoro")

    const callsAfterLoad = fetchSpy.mock.calls.length

    // Expand and collapse a couple of cards
    const toggles = screen.getAllByRole("button", {
      name: /zutaten anzeigen/i,
    })
    await user.click(toggles[0])
    await screen.findByText("600 g Pouletbrust")

    await user.click(
      screen.getByRole("button", { name: /zutaten verbergen/i })
    )
    await waitFor(() => {
      expect(screen.queryByText("600 g Pouletbrust")).not.toBeInTheDocument()
    })

    const togglesAgain = screen.getAllByRole("button", {
      name: /zutaten anzeigen/i,
    })
    await user.click(togglesAgain[1])
    await screen.findByText("400 g Spaghetti")

    const urls = fetchSpy.mock.calls.map(
      ([u]) => (typeof u === "string" ? u : (u as Request).url) as string
    )
    const recipeListCalls = urls.filter(
      (u) => u.includes("/api/recipes") && !u.includes("/api/recipes/")
    )
    expect(recipeListCalls).toHaveLength(1)
    expect(fetchSpy.mock.calls.length).toBe(callsAfterLoad)
  })
})
