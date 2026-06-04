import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/AppLayout"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import IngredientsPage from "./IngredientsPage"

function mockFetchResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

function buildFetchSpy(listIngredients: unknown, options?: {
  patchResponse?: unknown
  patchStatus?: number
  postResponse?: unknown
  postStatus?: number
  deleteStatus?: number
  deleteResponse?: unknown
}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url
    const method = init ? (init as RequestInit).method : undefined

    if (method === "DELETE" && url.startsWith("/api/ingredients/")) {
      if (options?.deleteStatus && options.deleteStatus !== 204) {
        return Promise.resolve(
          mockFetchResponse(
            options.deleteResponse ?? { detail: "Zutat wird verwendet" },
            { status: options.deleteStatus }
          )
        )
      }
      return Promise.resolve(new Response(null, { status: 204 }))
    }
    if (method === "POST" && url === "/api/ingredients") {
      return Promise.resolve(
        mockFetchResponse(
          options?.postResponse ?? {},
          { status: options?.postStatus ?? 201 }
        )
      )
    }
    if (method === "PATCH" && url.startsWith("/api/ingredients/")) {
      return Promise.resolve(
        mockFetchResponse(
          options?.patchResponse ?? listIngredients,
          { status: options?.patchStatus ?? 200 }
        )
      )
    }
    return Promise.resolve(mockFetchResponse(listIngredients))
  })
}

function renderInShell(ui: React.ReactNode, initialEntries = ["/ingredients"]) {
  const authValue: AuthContextType = {
    user: { id: 1, username: "alice", role: "admin", household_id: 1 },
    loading: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  }
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/ingredients" element={ui} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  )
}

interface IngredientConv {
  id: number
  name: string
  grams_per_el: number | null
  ml_per_el: number | null
  grams_per_tl: number | null
  ml_per_tl: number | null
  grams_per_msp: number | null
  ml_per_msp: number | null
  grams_per_pris: number | null
  ml_per_pris: number | null
}

const ingredientA: IngredientConv = {
  id: 1,
  name: "Mehl",
  grams_per_el: 12,
  ml_per_el: null,
  grams_per_tl: 4,
  ml_per_tl: null,
  grams_per_msp: null,
  ml_per_msp: null,
  grams_per_pris: null,
  ml_per_pris: null,
}

const ingredientB: IngredientConv = {
  id: 2,
  name: "Milch",
  grams_per_el: null,
  ml_per_el: 15,
  grams_per_tl: null,
  ml_per_tl: 5,
  grams_per_msp: null,
  ml_per_msp: null,
  grams_per_pris: null,
  ml_per_pris: null,
}

describe("IngredientsPage", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders the page with header 'Zutaten'", async () => {
    buildFetchSpy([ingredientA])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")
    expect(
      screen.getByRole("heading", { level: 1, name: "Zutaten" })
    ).toBeInTheDocument()
  })

  it("loads ingredients on mount and displays them in a table", async () => {
    buildFetchSpy([ingredientA, ingredientB])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")
    expect(screen.getByText("Milch")).toBeInTheDocument()

    expect(screen.getByText("12 g")).toBeInTheDocument()
    expect(screen.getByText("4 g")).toBeInTheDocument()
    expect(screen.getByText("15 ml")).toBeInTheDocument()
    expect(screen.getByText("5 ml")).toBeInTheDocument()
  })

  it("shows '—' for null conversion cells", async () => {
    buildFetchSpy([ingredientA])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")
    const dashes = screen.getAllByText("—")
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it("search input filters ingredients by name substring", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA, ingredientB])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    const searchInput = screen.getByPlaceholderText("Zutaten suchen...")
    await user.type(searchInput, "Mil")

    expect(screen.getByText("Milch")).toBeInTheDocument()
    expect(screen.queryByText("Mehl")).not.toBeInTheDocument()
  })

  it("clicking a conversion cell with a value enters edit mode", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    await user.click(screen.getByText("12 g"))

    const input = screen.getByDisplayValue("12")
    expect(input).toBeInTheDocument()
    expect(input.tagName).toBe("INPUT")
  })

  it("editing a conversion value and blurring PATCHes the ingredient", async () => {
    const user = userEvent.setup()
    const fetchSpy = buildFetchSpy([ingredientA])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    await user.click(screen.getByText("12 g"))

    const input = screen.getByDisplayValue("12") as HTMLInputElement
    await user.clear(input)
    await user.type(input, "15")
    await user.tab()

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/ingredients/1",
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining("grams_per_el"),
        })
      )
    })
  })

  it("clicking a '—' cell enters edit mode with empty input and unit selector", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    const dashes = screen.getAllByText("—")
    await user.click(dashes[0])

    const inputs = screen.getAllByRole("spinbutton")
    expect(inputs.length).toBeGreaterThan(0)
    expect((inputs[0] as HTMLInputElement).value).toBe("")
  })

  it("'New Ingredient' creates an ingredient via POST", async () => {
    const user = userEvent.setup()
    const fetchSpy = buildFetchSpy([ingredientA], {
      postResponse: { id: 99, name: "Zucker" },
    })

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    await user.click(screen.getByRole("button", { name: /neue zutat/i }))

    const nameInput = screen.getByPlaceholderText("Name der Zutat")
    await user.type(nameInput, "Zucker")
    await user.click(screen.getByRole("button", { name: /hinzufügen/i }))

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/ingredients",
        expect.objectContaining({ method: "POST" })
      )
    })
  })

  it("shows error when API returns an error on PATCH", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA], {
      patchResponse: {
        detail: "grams_per_el and ml_per_el cannot both be set",
      },
      patchStatus: 422,
    })

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    await user.click(screen.getByText("12 g"))

    const input = screen.getByDisplayValue("12") as HTMLInputElement
    await user.clear(input)
    await user.type(input, "10")
    await user.tab()

    expect(
      await screen.findByText(/grams_per_el and ml_per_el cannot both be set/i)
    ).toBeInTheDocument()
  })

  it("each ingredient row has a delete button", async () => {
    buildFetchSpy([ingredientA, ingredientB])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    const deleteButtons = screen.getAllByText("Löschen")
    expect(deleteButtons.length).toBe(2)
  })

  it("clicking delete shows confirmation dialog", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    const deleteButtons = screen.getAllByText("Löschen")
    await user.click(deleteButtons[0])

    const confirmButtons = screen.getAllByRole("button", { name: "Bestätigen" })
    expect(confirmButtons.length).toBeGreaterThan(0)
    const cancelButtons = screen.getAllByRole("button", { name: "Abbrechen" })
    expect(cancelButtons.length).toBeGreaterThan(0)
  })

  it("confirming delete removes ingredient from list", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA, ingredientB])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")
    expect(screen.getByText("Milch")).toBeInTheDocument()

    const deleteButtons = screen.getAllByText("Löschen")
    await user.click(deleteButtons[0])

    const confirmButtons = screen.getAllByRole("button", { name: "Bestätigen" })
    await user.click(confirmButtons[0])

    expect(screen.queryByText("Mehl")).not.toBeInTheDocument()
    expect(screen.getByText("Milch")).toBeInTheDocument()
  })

  it("delete blocked by references shows error message", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA], {
      deleteStatus: 409,
      deleteResponse: { detail: "Zutat wird verwendet von 3 Inventar-Einträgen" },
    })

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    const deleteButtons = screen.getAllByText("Löschen")
    await user.click(deleteButtons[0])
    const confirmButtons = screen.getAllByRole("button", { name: "Bestätigen" })
    await user.click(confirmButtons[0])

    expect(
      await screen.findByText(/Inventar-Einträgen/i)
    ).toBeInTheDocument()
  })

  it("clicking ingredient name enters edit mode", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    await user.click(screen.getByText("Mehl"))

    const input = screen.getByDisplayValue("Mehl")
    expect(input).toBeInTheDocument()
    expect(input.tagName).toBe("INPUT")
  })

  it("editing name and blurring PATCHes the ingredient", async () => {
    const user = userEvent.setup()
    const fetchSpy = buildFetchSpy([ingredientA])

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    await user.click(screen.getByText("Mehl"))

    const input = screen.getByDisplayValue("Mehl") as HTMLInputElement
    await user.clear(input)
    await user.type(input, "Vollkornmehl")
    await user.tab()

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/ingredients/1",
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining("Vollkornmehl"),
        })
      )
    })
  })

  it("renaming to duplicate shows error message", async () => {
    const user = userEvent.setup()
    buildFetchSpy([ingredientA], {
      patchResponse: { detail: "Ingredient already exists" },
      patchStatus: 409,
    })

    renderInShell(<IngredientsPage />)

    await screen.findByText("Mehl")

    await user.click(screen.getByText("Mehl"))

    const input = screen.getByDisplayValue("Mehl") as HTMLInputElement
    await user.clear(input)
    await user.type(input, "Milch")
    await user.tab()

    expect(
      await screen.findByText(/already exists/i)
    ).toBeInTheDocument()
  })
})
