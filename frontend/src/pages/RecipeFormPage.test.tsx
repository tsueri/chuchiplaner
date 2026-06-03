import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/AppLayout"
import { PageHeaderProvider } from "@/components/PageHeaderContext"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import RecipeFormPage from "./RecipeFormPage"
import RecipeListPage from "./RecipeListPage"

function renderForm(initialPath = "/recipes/new") {
  return render(
    <PageHeaderProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/recipes/new" element={<RecipeFormPage />} />
          <Route
            path="/recipes/:id"
            element={<div>recipe-detail-stub</div>}
          />
          <Route path="/recipes" element={<RecipeListPage />} />
        </Routes>
      </MemoryRouter>
    </PageHeaderProvider>
  )
}

function renderListInShell() {
  const authValue: AuthContextType = {
    user: { id: 1, username: "alice", role: "admin", household_id: 1 },
    loading: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  }
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={["/recipes"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/recipes" element={<RecipeListPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
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

describe("RecipeFormPage", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders all six fields with Speichern disabled on a blank form", () => {
    renderForm()

    expect(screen.getByLabelText(/titel/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/zubereitung/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/portionen/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/bild-?url|bild/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^quelle$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/quell-domain|domain/i)).toBeInTheDocument()

    const saveButton = screen.getByRole("button", { name: /speichern/i })
    expect(saveButton).toBeDisabled()
  })

  it("enables Speichern once title and instructions are non-empty", async () => {
    const user = userEvent.setup()
    renderForm()

    const saveButton = screen.getByRole("button", { name: /speichern/i })
    expect(saveButton).toBeDisabled()

    await user.type(screen.getByLabelText(/titel/i), "Pasta")
    expect(saveButton).toBeDisabled()

    await user.type(screen.getByLabelText(/zubereitung/i), "Kochen.")
    expect(saveButton).toBeEnabled()
  })

  it("POSTs to /api/recipes with the contract body and navigates to the new detail page", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        mockFetchResponse({ id: 42, title: "Pasta" }, { status: 201 })
      )

    renderForm()

    await user.type(screen.getByLabelText(/titel/i), "Pasta")
    await user.type(screen.getByLabelText(/zubereitung/i), "Wasser kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    await waitFor(() => {
      expect(screen.getByText("recipe-detail-stub")).toBeInTheDocument()
    })

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/recipes")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body as string)).toEqual({
      title: "Pasta",
      instructions: "Wasser kochen.",
      servings: 4,
      image_url: null,
      source_url: null,
      source_domain: null,
      ingredients: [],
    })
  })

  it("renders the API error detail inline and does not navigate", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      mockFetchResponse(
        { detail: "Title ist zu lang." },
        { status: 422 }
      )
    )

    renderForm()

    await user.type(screen.getByLabelText(/titel/i), "X")
    await user.type(screen.getByLabelText(/zubereitung/i), "Y")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    expect(await screen.findByText("Title ist zu lang.")).toBeInTheDocument()
    expect(screen.queryByText("recipe-detail-stub")).not.toBeInTheDocument()
  })

  it("derives source_domain from source_url on blur when domain is empty", async () => {
    const user = userEvent.setup()
    renderForm()

    const sourceUrl = screen.getByLabelText(/^quelle$/i)
    const sourceDomain = screen.getByLabelText(/quell-domain|domain/i)

    await user.type(sourceUrl, "https://www.fooby.ch/pasta")
    sourceUrl.blur()

    await waitFor(() => {
      expect((sourceDomain as HTMLInputElement).value).toBe("www.fooby.ch")
    })
  })

  it("RecipeListPage exposes a 'Neues Rezept' action that links to /recipes/new", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/tags")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderListInShell()

    const newButton = await screen.findByRole("link", {
      name: /neues rezept/i,
    })
    expect(newButton).toHaveAttribute("href", "/recipes/new")
  })
})
