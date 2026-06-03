import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { PageHeaderProvider } from "@/components/PageHeaderContext"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import RecipeDetailPage from "./RecipeDetailPage"

interface FetchCall {
  url: string
  method: string
  body: string | null
}

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

function renderDetail(
  recipe: unknown,
  options: {
    userRole?: string
    putResponse?: unknown
    putStatus?: number
    tags?: { id: number; name: string; group: string; household_id: number | null }[]
  } = {}
) {
  const authValue: AuthContextType = {
    user: {
      id: 1,
      username: "alice",
      role: options.userRole ?? "admin",
      household_id: 1,
    },
    loading: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  }
  const fetchCalls: FetchCall[] = []
  const tags = options.tags ?? []
  const putStatus = options.putStatus ?? 200
  const putResponse =
    options.putResponse !== undefined ? options.putResponse : recipe

  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url =
      typeof input === "string" ? input : (input as Request).url
    const method = (init?.method ?? "GET").toUpperCase()
    const body = init?.body ? String(init.body) : null
    fetchCalls.push({ url, method, body })
    if (method === "PUT" && url === "/api/recipes/1") {
      return Promise.resolve(
        jsonResponse(putResponse, { status: putStatus })
      )
    }
    if (url === "/api/recipes/1") {
      return Promise.resolve(jsonResponse(recipe))
    }
    if (url === "/api/recipes/1/notes") {
      return Promise.resolve(jsonResponse([]))
    }
    if (url === "/api/tags") {
      return Promise.resolve(jsonResponse(tags))
    }
    return Promise.resolve(jsonResponse({}))
  })

  const view = render(
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
  return { ...view, fetchCalls }
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
  ingredients: [],
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

describe("RecipeDetailPage inline edit mode", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("shows a 'Bearbeiten' button to authenticated users in read mode", async () => {
    renderDetail({ ...baseRecipe })

    expect(
      await screen.findByRole("button", { name: /bearbeiten/i })
    ).toBeInTheDocument()
  })

  it("Speichern PUTs the full state to /api/recipes/:id and exits edit mode on success", async () => {
    const user = userEvent.setup()
    const recipe = {
      ...baseRecipe,
      title: "Original",
      instructions: "Anbraten.",
      servings: 4,
      ingredients: [
        {
          id: 10,
          ingredient_id: 100,
          quantity: 600,
          unit: "g",
          ingredient_name: "Pouletbrust",
          order_index: 0,
        },
      ],
    }
    const { fetchCalls } = renderDetail(recipe, {
      putResponse: { ...recipe, title: "Bearbeitet" },
    })

    await user.click(
      await screen.findByRole("button", { name: /bearbeiten/i })
    )

    const titleInput = screen.getByLabelText(/titel/i) as HTMLInputElement
    await user.clear(titleInput)
    await user.type(titleInput, "Bearbeitet")

    const saveButton = screen.getByRole("button", { name: /speichern/i })
    await user.click(saveButton)

    await waitFor(() => {
      const put = fetchCalls.find(
        (c) => c.method === "PUT" && c.url === "/api/recipes/1"
      )
      expect(put).toBeDefined()
      const body = JSON.parse(put!.body!) as Record<string, unknown>
      expect(body.title).toBe("Bearbeitet")
      expect(body.ingredients).toEqual([
        { ingredient_id: 100, quantity: 600, unit: "g", order_index: 0 },
      ])
    })

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Bearbeitet",
      })
    ).toBeInTheDocument()
    expect(screen.queryByLabelText("Titel")).toBeNull()
  })

  it("Abbrechen discards local edits and returns to read mode showing the original state", async () => {
    const user = userEvent.setup()
    const recipe = { ...baseRecipe, title: "Original" }
    renderDetail(recipe)

    await user.click(
      await screen.findByRole("button", { name: /bearbeiten/i })
    )

    const titleInput = screen.getByLabelText("Titel") as HTMLInputElement
    await user.clear(titleInput)
    await user.type(titleInput, "Verworfen")

    await user.click(screen.getByRole("button", { name: /^abbrechen$/i }))

    expect(
      await screen.findByRole("heading", { level: 1, name: "Original" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /bearbeiten/i })
    ).toBeInTheDocument()
  })

  it("renders a server error inline in edit mode and preserves local edits", async () => {
    const user = userEvent.setup()
    const recipe = { ...baseRecipe, title: "Original" }
    renderDetail(recipe, {
      putStatus: 400,
      putResponse: { detail: "Bad ingredient id" },
    })

    await user.click(
      await screen.findByRole("button", { name: /bearbeiten/i })
    )

    const titleInput = screen.getByLabelText("Titel") as HTMLInputElement
    await user.clear(titleInput)
    await user.type(titleInput, "Bleibt")

    await user.click(screen.getByRole("button", { name: /^speichern$/i }))

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("Bad ingredient id")

    const titleAfter = screen.getByLabelText("Titel") as HTMLInputElement
    expect(titleAfter.value).toBe("Bleibt")
  })

  it("hides the favorite star and notes section in edit mode", async () => {
    const user = userEvent.setup()
    const recipe = { ...baseRecipe, is_favorited: true }
    renderDetail(recipe)

    expect(
      await screen.findByTitle("Favorit entfernen")
    ).toBeInTheDocument()
    expect(
      await screen.findByRole("heading", { name: /notizen/i })
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole("button", { name: /bearbeiten/i })
    )

    expect(screen.queryByTitle("Favorit entfernen")).toBeNull()
    expect(screen.queryByTitle("Favorit")).toBeNull()
    expect(
      screen.queryByRole("heading", { name: /notizen/i })
    ).toBeNull()
  })

  it("shows the admin delete button only in read mode and only to admins", async () => {
    const user = userEvent.setup()
    renderDetail({ ...baseRecipe }, { userRole: "admin" })

    expect(
      await screen.findByRole("button", { name: /rezept löschen/i })
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole("button", { name: /bearbeiten/i })
    )

    expect(
      screen.queryByRole("button", { name: /rezept löschen/i })
    ).toBeNull()

    await user.click(screen.getByRole("button", { name: /^abbrechen$/i }))

    expect(
      await screen.findByRole("button", { name: /rezept löschen/i })
    ).toBeInTheDocument()
  })

  it("does not show the admin delete button to non-admin users", async () => {
    renderDetail({ ...baseRecipe }, { userRole: "member" })

    expect(
      await screen.findByRole("heading", { level: 1, name: "Pouletgeschnetzeltes" })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /rezept löschen/i })
    ).toBeNull()
  })
})
