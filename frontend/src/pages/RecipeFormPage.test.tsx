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
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      return Promise.reject(new Error(`Unhandled fetch in test: ${url}`))
    })
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
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(mockFetchResponse([]))
        }
        if (url === "/api/recipes") {
          return Promise.resolve(
            mockFetchResponse({ id: 42, title: "Pasta" }, { status: 201 })
          )
        }
        return Promise.resolve(mockFetchResponse([]))
      })

    renderForm()

    await user.type(screen.getByLabelText(/titel/i), "Pasta")
    await user.type(screen.getByLabelText(/zubereitung/i), "Wasser kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    await waitFor(() => {
      expect(screen.getByText("recipe-detail-stub")).toBeInTheDocument()
    })

    const recipeCall = fetchSpy.mock.calls.find(
      ([u]) => u === "/api/recipes"
    ) as [string, RequestInit]
    expect(recipeCall).toBeDefined()
    const [, init] = recipeCall
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
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url === "/api/recipes") {
        return Promise.resolve(
          mockFetchResponse(
            { detail: "Title ist zu lang." },
            { status: 422 }
          )
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

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

describe("RecipeFormPage ingredient rows", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      return Promise.reject(new Error(`Unhandled fetch in test: ${url}`))
    })
  })

  it("'Zutat hinzufügen' appends an empty row; each row has a remove button", async () => {
    const user = userEvent.setup()
    renderForm()

    expect(screen.queryByRole("combobox", { name: /zutat/i })).not.toBeInTheDocument()

    await user.click(
      screen.getByRole("button", { name: /zutat hinzufügen/i })
    )

    expect(screen.getByRole("combobox", { name: /zutat/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/menge/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/einheit/i)).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /zutat entfernen/i })
    ).toBeInTheDocument()
  })

  it("typing in the combobox debounces and queries /api/ingredients?q=…", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockFetchResponse([]))

    renderForm()
    await user.click(
      screen.getByRole("button", { name: /zutat hinzufügen/i })
    )

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
      const url = typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/ingredients")) {
        return Promise.resolve(
          mockFetchResponse([{ id: 7, name: "Tomaten" }])
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm()
    await user.click(
      screen.getByRole("button", { name: /zutat hinzufügen/i })
    )

    const combobox = screen.getByRole("combobox", { name: /zutat/i })
    await user.type(combobox, "Tom")
    const option = await screen.findByRole("option", { name: /tomaten/i })
    await user.click(option)

    expect(screen.getByText("Tomaten")).toBeInTheDocument()
    expect(
      screen.queryByRole("combobox", { name: /zutat/i })
    ).not.toBeInTheDocument()
  })

  it("submits fully-filled rows with order_index + parsed quantity; drops empty rows", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url = typeof input === "string" ? input : (input as Request).url
        if (url.includes("/api/ingredients")) {
          return Promise.resolve(
            mockFetchResponse([
              { id: 1, name: "Tomaten" },
              { id: 2, name: "Zwiebeln" },
            ])
          )
        }
        if (url === "/api/recipes") {
          return Promise.resolve(
            mockFetchResponse({ id: 99, title: "Pasta" }, { status: 201 })
          )
        }
        return Promise.resolve(mockFetchResponse([]))
      })

    renderForm()
    await user.type(screen.getByLabelText(/titel/i), "Pasta")
    await user.type(screen.getByLabelText(/zubereitung/i), "Kochen.")

    // Add 3 rows: row 0 filled, row 1 left empty, row 2 filled
    await user.click(
      screen.getByRole("button", { name: /zutat hinzufügen/i })
    )
    await user.click(
      screen.getByRole("button", { name: /zutat hinzufügen/i })
    )
    await user.click(
      screen.getByRole("button", { name: /zutat hinzufügen/i })
    )

    // Row 0: Tomaten / 500 / g
    let comboboxes = screen.getAllByRole("combobox", { name: /zutat/i })
    await user.type(comboboxes[0], "Tom")
    await user.click(
      await screen.findByRole("option", { name: /tomaten/i })
    )
    let mengen = screen.getAllByLabelText(/menge/i)
    await user.type(mengen[0], "500")

    // Row 1 stays empty (will be dropped on submit)

    // Row 2: Zwiebeln / 1 / Stück
    comboboxes = screen.getAllByRole("combobox", { name: /zutat/i })
    await user.type(comboboxes[1], "Zwi")
    await user.click(
      await screen.findByRole("option", { name: /zwiebeln/i })
    )
    mengen = screen.getAllByLabelText(/menge/i)
    const units = screen.getAllByLabelText(/einheit/i)
    await user.selectOptions(units[2], "Stück")
    await user.type(mengen[2], "1")

    await user.click(screen.getByRole("button", { name: /speichern/i }))

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/recipes",
        expect.objectContaining({ method: "POST" })
      )
    })

    const recipeCall = fetchSpy.mock.calls.find(
      ([u]) => u === "/api/recipes"
    ) as [string, RequestInit]
    const body = JSON.parse(recipeCall[1].body as string)
    expect(body.ingredients).toEqual([
      { ingredient_id: 1, quantity: 500, unit: "g", order_index: 0 },
      { ingredient_id: 2, quantity: 1, unit: "Stück", order_index: 1 },
    ])
  })
})

describe("RecipeFormPage tag picker", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      return Promise.reject(new Error(`Unhandled fetch in test: ${url}`))
    })
  })

  it("fetches /api/tags on mount and renders the tags as toggle pills", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(
            mockFetchResponse([
              {
                id: 1,
                name: "Frühling",
                group: "season",
                household_id: null,
              },
              {
                id: 2,
                name: "Poulet",
                group: "ingredient",
                household_id: 1,
              },
            ])
          )
        }
        return Promise.resolve(mockFetchResponse([]))
      })

    renderForm()

    const pill1 = await screen.findByRole("button", { name: /frühling/i })
    const pill2 = await screen.findByRole("button", { name: /poulet/i })
    expect(pill1).toBeInTheDocument()
    expect(pill2).toBeInTheDocument()

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/tags",
      expect.objectContaining({ credentials: "same-origin" })
    )
  })

  it("clicking a tag pill marks it as selected (aria-pressed=true)", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(
          mockFetchResponse([
            {
              id: 1,
              name: "Frühling",
              group: "season",
              household_id: null,
            },
          ])
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm()

    const pill = await screen.findByRole("button", { name: /frühling/i })
    expect(pill).toHaveAttribute("aria-pressed", "false")

    await user.click(pill)

    expect(pill).toHaveAttribute("aria-pressed", "true")
  })

  it("clicking an already-selected tag pill deselects it (aria-pressed=false)", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(
          mockFetchResponse([
            {
              id: 1,
              name: "Frühling",
              group: "season",
              household_id: null,
            },
          ])
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm()

    const pill = await screen.findByRole("button", { name: /frühling/i })
    await user.click(pill)
    expect(pill).toHaveAttribute("aria-pressed", "true")

    await user.click(pill)
    expect(pill).toHaveAttribute("aria-pressed", "false")
  })

  it("submit with no tags selected fires only the POST (no PUT)", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(
            mockFetchResponse([
              {
                id: 1,
                name: "Frühling",
                group: "season",
                household_id: null,
              },
            ])
          )
        }
        if (url === "/api/recipes") {
          return Promise.resolve(
            mockFetchResponse(
              { id: 42, title: "Pasta" },
              { status: 201 }
            )
          )
        }
        return Promise.reject(
          new Error(`Unexpected fetch in test: ${url}`)
        )
      })

    renderForm()

    // Wait for tags to load (and assert no toggle happened)
    await screen.findByRole("button", { name: /frühling/i })

    await user.type(screen.getByLabelText(/titel/i), "Pasta")
    await user.type(screen.getByLabelText(/zubereitung/i), "Wasser kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    await waitFor(() => {
      expect(screen.getByText("recipe-detail-stub")).toBeInTheDocument()
    })

    const calls = fetchSpy.mock.calls.map(([u]) => u as string)
    expect(calls).toEqual(["/api/tags", "/api/recipes"])
    expect(calls).not.toContain("/api/recipes/42")
  })

  it("submit with tags selected fires POST then PUT { tag_ids } in that order", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(
            mockFetchResponse([
              {
                id: 1,
                name: "Frühling",
                group: "season",
                household_id: null,
              },
              {
                id: 2,
                name: "Poulet",
                group: "ingredient",
                household_id: 1,
              },
            ])
          )
        }
        if (url === "/api/recipes") {
          return Promise.resolve(
            mockFetchResponse(
              { id: 42, title: "Pasta" },
              { status: 201 }
            )
          )
        }
        if (url === "/api/recipes/42") {
          return Promise.resolve(
            mockFetchResponse({ id: 42, title: "Pasta" })
          )
        }
        return Promise.reject(
          new Error(`Unexpected fetch in test: ${url}`)
        )
      })

    renderForm()

    const frühlingPill = await screen.findByRole("button", {
      name: /frühling/i,
    })
    const pouletPill = await screen.findByRole("button", { name: /poulet/i })
    await user.click(frühlingPill)
    await user.click(pouletPill)

    await user.type(screen.getByLabelText(/titel/i), "Pasta")
    await user.type(screen.getByLabelText(/zubereitung/i), "Wasser kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    await waitFor(() => {
      expect(screen.getByText("recipe-detail-stub")).toBeInTheDocument()
    })

    const recipePutCallIdx = fetchSpy.mock.calls.findIndex(
      ([u]) => u === "/api/recipes/42"
    )
    expect(recipePutCallIdx).toBeGreaterThan(-1)

    const [, putInit] = fetchSpy.mock.calls[recipePutCallIdx] as [
      string,
      RequestInit
    ]
    expect(putInit.method).toBe("PUT")
    expect(JSON.parse(putInit.body as string)).toEqual({
      tag_ids: [1, 2],
    })

    // Sequence check: tags → POST → PUT
    const urls = fetchSpy.mock.calls.map(([u]) => u as string)
    const postIdx = urls.indexOf("/api/recipes")
    const putIdx = urls.indexOf("/api/recipes/42")
    expect(postIdx).toBeLessThan(putIdx)
  })

  it("PUT failure renders the error inline and does not navigate (recipe was created)", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(
            mockFetchResponse([
              {
                id: 1,
                name: "Frühling",
                group: "season",
                household_id: null,
              },
            ])
          )
        }
        if (url === "/api/recipes") {
          return Promise.resolve(
            mockFetchResponse(
              { id: 42, title: "Pasta" },
              { status: 201 }
            )
          )
        }
        if (url === "/api/recipes/42") {
          return Promise.resolve(
            mockFetchResponse(
              { detail: "Tag konnte nicht zugewiesen werden." },
              { status: 422 }
            )
          )
        }
        return Promise.reject(
          new Error(`Unexpected fetch in test: ${url}`)
        )
      })

    renderForm()

    const pill = await screen.findByRole("button", { name: /frühling/i })
    await user.click(pill)

    await user.type(screen.getByLabelText(/titel/i), "Pasta")
    await user.type(screen.getByLabelText(/zubereitung/i), "Wasser kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    expect(
      await screen.findByText("Tag konnte nicht zugewiesen werden.")
    ).toBeInTheDocument()
    expect(screen.queryByText("recipe-detail-stub")).not.toBeInTheDocument()

    // POST was called, so the recipe exists server-side
    const urls = fetchSpy.mock.calls.map(([u]) => u as string)
    expect(urls).toContain("/api/recipes")
    expect(urls).toContain("/api/recipes/42")

    // Submit button is re-enabled so the user could try to fix tags and re-submit
    expect(
      screen.getByRole("button", { name: /speichern/i })
    ).toBeEnabled()
  })
})
