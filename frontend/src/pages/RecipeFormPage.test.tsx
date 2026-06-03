import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"

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

function RecipeFormRouteStub() {
  const loc = useLocation()
  return (
    <div data-testid="recipe-form-stub" data-search={loc.search}>
      recipe-form-stub
    </div>
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
            <Route path="/recipes/new" element={<RecipeFormRouteStub />} />
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
      learned_aliases: [],
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

  it("shows a hard duplicate error with link when 409 is returned, blocks Speichern until source_url changes", async () => {
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
            {
              detail: "Duplikat: Ein Rezept mit der URL https://example.com/dup existiert bereits in diesem Haushalt.",
              existing_recipe_id: 7,
            },
            { status: 409 }
          )
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm()

    await user.type(screen.getByLabelText(/titel/i), "Pasta")
    await user.type(screen.getByLabelText(/zubereitung/i), "Kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    expect(
      await screen.findByText(/du hast dieses rezept schon importiert/i)
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /zum bestehenden rezept/i })
    ).toHaveAttribute("href", "/recipes/7")

    // Speichern is disabled because duplicateBlocked is true
    expect(
      screen.getByRole("button", { name: /speichern/i })
    ).toBeDisabled()

    // Changing the source_url should re-enable Speichern
    const sourceUrl = screen.getByLabelText(/^quelle$/i)
    await user.clear(sourceUrl)
    await user.type(sourceUrl, "https://example.com/other")

    expect(
      screen.getByRole("button", { name: /speichern/i })
    ).toBeEnabled()
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

describe("RecipeFormPage URL import", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url.includes("/api/ingredients")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      return Promise.reject(new Error(`Unhandled fetch in test: ${url}`))
    })
  })

  it("does NOT call /api/recipes/import when no url query param is present", () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(mockFetchResponse([]))
        }
        return Promise.reject(new Error(`Unhandled fetch in test: ${url}`))
      })

    renderForm("/recipes/new")

    const urls = fetchSpy.mock.calls.map(([u]) => u as string)
    expect(urls).not.toContain("/api/recipes/import")
  })

  it("prefills the form and shows the 'Importiert von' banner on a successful import", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input, init) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(mockFetchResponse([]))
        }
        if (url === "/api/recipes/import") {
          const body = JSON.parse(init?.body as string)
          expect(body).toEqual({ url: "https://www.fooby.ch/recipe" })
          return Promise.resolve(
            mockFetchResponse({
              title: "Fooby Pasta",
              ingredients: [
                { raw: "Tomaten", name: "Tomaten", quantity: null, unit: null, ingredient_id: null, confidence: 0.0 },
                { raw: "Zwiebeln", name: "Zwiebeln", quantity: null, unit: null, ingredient_id: null, confidence: 0.0 },
              ],
              instructions: "Alles mischen.",
              image_url: "https://example.com/img.jpg",
              servings: 2,
              source_url: "https://www.fooby.ch/recipe",
              source_domain: "www.fooby.ch",
              is_partial: false,
            })
          )
        }
        return Promise.resolve(mockFetchResponse([]))
      })

    renderForm("/recipes/new?url=" + encodeURIComponent("https://www.fooby.ch/recipe"))

    await waitFor(() => {
      expect(
        screen.getByText(/importiert von www\.fooby\.ch/i)
      ).toBeInTheDocument()
    })

    expect(
      (screen.getByLabelText(/titel/i) as HTMLInputElement).value
    ).toBe("Fooby Pasta")
    expect(
      (screen.getByLabelText(/zubereitung/i) as HTMLTextAreaElement).value
    ).toBe("Alles mischen.")
    expect(
      (screen.getByLabelText(/portionen/i) as HTMLInputElement).value
    ).toBe("2")
    expect(
      (screen.getByLabelText(/^quelle$/i) as HTMLInputElement).value
    ).toBe("https://www.fooby.ch/recipe")
    expect(
      (screen.getByLabelText(/quell-domain|domain/i) as HTMLInputElement).value
    ).toBe("www.fooby.ch")

    const importCall = fetchSpy.mock.calls.find(
      ([u]) => u === "/api/recipes/import"
    )
    expect(importCall).toBeDefined()
  })

  it("'Verwerfen' link clears the prefilled state and removes the url query param", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url === "/api/recipes/import") {
        return Promise.resolve(
          mockFetchResponse({
            title: "Fooby Pasta",
            ingredients: [],
            instructions: "Alles mischen.",
            image_url: null,
            servings: 4,
            source_url: "https://www.fooby.ch/recipe",
            source_domain: "www.fooby.ch",
            is_partial: false,
          })
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm("/recipes/new?url=" + encodeURIComponent("https://www.fooby.ch/recipe"))

    await screen.findByText(/importiert von www\.fooby\.ch/i)

    const verwerfenLink = screen.getByRole("button", { name: /verwerfen/i })
    expect(verwerfenLink).toBeInTheDocument()

    await userEvent.setup().click(verwerfenLink)

    expect(
      screen.queryByText(/importiert von www\.fooby\.ch/i)
    ).not.toBeInTheDocument()
    expect(
      (screen.getByLabelText(/titel/i) as HTMLInputElement).value
    ).toBe("")
    expect(
      (screen.getByLabelText(/zubereitung/i) as HTMLTextAreaElement).value
    ).toBe("")
  })

  it("renders the import error inline and leaves the form blank on a 422", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url === "/api/recipes/import") {
        return Promise.resolve(
          mockFetchResponse(
            { detail: "Could not extract recipe from this URL" },
            { status: 422 }
          )
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://unsupported.example/x")
    )

    expect(
      await screen.findByText("Could not extract recipe from this URL")
    ).toBeInTheDocument()

    expect(
      screen.queryByText(/importiert von/i)
    ).not.toBeInTheDocument()
    expect(
      (screen.getByLabelText(/titel/i) as HTMLInputElement).value
    ).toBe("")
    expect(
      (screen.getByLabelText(/zubereitung/i) as HTMLTextAreaElement).value
    ).toBe("")
  })

  it("renders imported rows in three confidence bands (locked chip, highlighted suggestion, open combobox)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url === "/api/recipes/import") {
        return Promise.resolve(
          mockFetchResponse({
            title: "Test",
            instructions: "Mix.",
            image_url: null,
            servings: 2,
            source_url: "https://example.com/test",
            source_domain: "example.com",
            is_partial: false,
            existing_recipe_id: null,
            ingredients: [
              {
                raw: "Tomaten",
                name: "Tomaten",
                quantity: 500,
                unit: "g",
                ingredient_id: 7,
                confidence: 1.0,
              },
              {
                raw: "Zwiebel",
                name: "Zwiebeln",
                quantity: 2,
                unit: "Stück",
                ingredient_id: 8,
                confidence: 0.8,
              },
              {
                raw: "600g Kalbfleisch",
                name: "Kalbfleisch",
                quantity: 600,
                unit: "g",
                ingredient_id: null,
                confidence: 0.0,
              },
            ],
          })
        )
      }
      if (url.includes("/api/ingredients?q=Zwiebel")) {
        return Promise.resolve(
          mockFetchResponse([
            { id: 8, name: "Zwiebeln" },
            { id: 9, name: "Zwiebeln rot" },
          ])
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://example.com/test")
    )

    await screen.findByText(/importiert von example\.com/i)

    // Three rows exist
    expect(
      screen.getAllByRole("button", { name: /zutat entfernen/i })
    ).toHaveLength(3)

    // Band 1: Locked chip with ↻ override button
    expect(
      screen.getByRole("button", { name: /zutat ändern/i })
    ).toBeInTheDocument()

    // Band 2+3: Two combobox inputs
    const comboboxes = screen.getAllByRole("combobox", { name: /zutat/i })
    expect(comboboxes).toHaveLength(2)
    expect((comboboxes[0] as HTMLInputElement).value).toBe("Zwiebel")
    expect((comboboxes[1] as HTMLInputElement).value).toBe("600g Kalbfleisch")

    // Band 2: Highlighted suggestion and "Anderer Vorschlag…"
    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeInTheDocument()
    }, { timeout: 3000 })
    const listbox = screen.getByRole("listbox")
    const options = listbox.querySelectorAll('[role="option"]')
    const highlighted = Array.from(options).find(
      (o) => o.getAttribute("aria-selected") === "true"
    )
    expect(highlighted).toBeDefined()
    expect(highlighted).toHaveTextContent("Zwiebeln")
    expect(
      screen.getByRole("option", { name: /anderer vorschlag/i })
    ).toBeInTheDocument()
    expect(highlighted).toHaveTextContent("Zwiebeln")
    expect(
      screen.getByRole("option", { name: /anderer vorschlag/i })
    ).toBeInTheDocument()

    // Prefilled quantities and units
    const menges = screen.getAllByLabelText(/menge/i) as HTMLInputElement[]
    expect(menges[0].value).toBe("500")
    expect(menges[1].value).toBe("2")
    expect(menges[2].value).toBe("600")

    const unitSelects = screen.getAllByLabelText(/einheit/i) as HTMLSelectElement[]
    expect(unitSelects[0].value).toBe("g")
    expect(unitSelects[1].value).toBe("Stück")
    expect(unitSelects[2].value).toBe("g")

    // Raw text is visible on each row
    expect(screen.getByText("Zwiebel")).toBeInTheDocument()
    expect(screen.getByText("600g Kalbfleisch")).toBeInTheDocument()
  })

  it("'↻' override button on a locked chip unlocks the row and opens the catalog search", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url === "/api/recipes/import") {
        return Promise.resolve(
          mockFetchResponse({
            title: "Test",
            instructions: "Mix.",
            image_url: null,
            servings: 2,
            source_url: "https://example.com/test",
            source_domain: "example.com",
            is_partial: false,
            existing_recipe_id: null,
            ingredients: [
              {
                raw: "Tomaten",
                name: "Tomaten",
                quantity: 500,
                unit: "g",
                ingredient_id: 7,
                confidence: 1.0,
              },
            ],
          })
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    const user = userEvent.setup()
    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://example.com/test")
    )

    await screen.findByText(/importiert von example\.com/i)

    // Band 1: Locked chip, no combobox
    expect(
      screen.getByRole("button", { name: /zutat ändern/i })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("combobox", { name: /zutat/i })
    ).not.toBeInTheDocument()

    // Click ↻
    await user.click(screen.getByRole("button", { name: /zutat ändern/i }))

    // Now combobox appears with the ingredient name
    const combobox = screen.getByRole("combobox", { name: /zutat/i })
    expect(combobox).toBeInTheDocument()
    expect((combobox as HTMLInputElement).value).toBe("Tomaten")

    // Locked chip override button is gone
    expect(
      screen.queryByRole("button", { name: /zutat ändern/i })
    ).not.toBeInTheDocument()
  })

  it("'Verwerfen' clears imported rows in addition to basic fields", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url === "/api/recipes/import") {
        return Promise.resolve(
          mockFetchResponse({
            title: "Test",
            instructions: "Mix.",
            image_url: null,
            servings: 2,
            source_url: "https://example.com/test",
            source_domain: "example.com",
            is_partial: false,
            existing_recipe_id: null,
            ingredients: [
              {
                raw: "Tomaten",
                name: "Tomaten",
                quantity: 500,
                unit: "g",
                ingredient_id: 7,
                confidence: 1.0,
              },
              {
                raw: "Zwiebel",
                name: "Zwiebeln",
                quantity: 2,
                unit: "Stück",
                ingredient_id: 8,
                confidence: 0.8,
              },
            ],
          })
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    const user = userEvent.setup()
    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://example.com/test")
    )

    await screen.findByText(/importiert von example\.com/i)

    // Rows are present
    expect(
      screen.getAllByRole("button", { name: /zutat entfernen/i })
    ).toHaveLength(2)

    // Click Verwerfen
    await user.click(screen.getByRole("button", { name: /verwerfen/i }))

    // Rows are cleared
    expect(
      screen.queryByRole("button", { name: /zutat entfernen/i })
    ).not.toBeInTheDocument()

    // Form cleared
    expect((screen.getByLabelText(/titel/i) as HTMLInputElement).value).toBe("")
    expect(
      (screen.getByLabelText(/zubereitung/i) as HTMLTextAreaElement).value
    ).toBe("")
  })

  it("renders a soft duplicate warning with link when import carries existing_recipe_id", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url === "/api/recipes/import") {
        return Promise.resolve(
          mockFetchResponse({
            title: "Fooby Pasta",
            ingredients: [],
            instructions: "Alles mischen.",
            image_url: null,
            servings: 4,
            source_url: "https://www.fooby.ch/recipe",
            source_domain: "www.fooby.ch",
            existing_recipe_id: 7,
            is_partial: false,
          })
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://www.fooby.ch/recipe")
    )

    await screen.findByText(/du hast dieses rezept schon importiert/i)
    expect(
      screen.getByRole("link", { name: /zum bestehenden rezept/i })
    ).toHaveAttribute("href", "/recipes/7")

    // Import banner still renders
    expect(
      screen.getByText(/importiert von www\.fooby\.ch/i)
    ).toBeInTheDocument()

    // Speichern is still enabled (soft warning does not block save)
    expect(
      screen.getByRole("button", { name: /speichern/i })
    ).not.toBeDisabled()
  })

  it("sends learned_aliases for fuzzy-accepted rows (0.6 ≤ confidence < 1.0)", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(mockFetchResponse([]))
        }
        if (url === "/api/recipes/import") {
          return Promise.resolve(
            mockFetchResponse({
              title: "Test",
              instructions: "Mix.",
              image_url: null,
              servings: 2,
              source_url: "https://example.com/test",
              source_domain: "example.com",
              is_partial: false,
              existing_recipe_id: null,
              ingredients: [
                {
                  raw: "Zwiebel",
                  name: "Zwiebeln",
                  quantity: 2,
                  unit: "Stück",
                  ingredient_id: 8,
                  confidence: 0.8,
                },
              ],
            })
          )
        }
        if (url.includes("/api/ingredients?q=Zwiebel")) {
          return Promise.resolve(
            mockFetchResponse([
              { id: 8, name: "Zwiebeln" },
            ])
          )
        }
        if (url === "/api/recipes") {
          return Promise.resolve(
            mockFetchResponse({ id: 42, title: "Test" }, { status: 201 })
          )
        }
        return Promise.resolve(mockFetchResponse([]))
      })

    const user = userEvent.setup()
    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://example.com/test")
    )

    await screen.findByText(/importiert von example\.com/i)

    // The fuzzy row shows a combobox with suggestion dropdown
    const listbox = await screen.findByRole("listbox")
    const suggested = Array.from(
      listbox.querySelectorAll('[role="option"]')
    ).find((o) => o.getAttribute("aria-selected") === "true")
    expect(suggested).toBeDefined()
    expect(suggested).toHaveTextContent("Zwiebeln")

    // Accept the fuzzy suggestion
    await user.click(suggested!)

    await user.type(screen.getByLabelText(/zubereitung/i), "Kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    await waitFor(() => {
      expect(screen.getByText("recipe-detail-stub")).toBeInTheDocument()
    })

    const recipeCall = fetchSpy.mock.calls.find(
      ([u]) => u === "/api/recipes"
    ) as [string, RequestInit]
    const body = JSON.parse(recipeCall[1].body as string)
    expect(body.learned_aliases).toEqual([
      { alias_name: "Zwiebel", ingredient_id: 8 },
    ])
  })

  it("sends learned_aliases for overridden rows (user changed from suggestion)", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(mockFetchResponse([]))
        }
        if (url === "/api/recipes/import") {
          return Promise.resolve(
            mockFetchResponse({
              title: "Test",
              instructions: "Mix.",
              image_url: null,
              servings: 2,
              source_url: "https://example.com/test",
              source_domain: "example.com",
              is_partial: false,
              existing_recipe_id: null,
              ingredients: [
                {
                  raw: "Tomaten",
                  name: "Tomaten",
                  quantity: 500,
                  unit: "g",
                  ingredient_id: 7,
                  confidence: 1.0,
                },
              ],
            })
          )
        }
        if (url.includes("/api/ingredients?q=Tomaten")) {
          return Promise.resolve(
            mockFetchResponse([
              { id: 7, name: "Tomaten" },
              { id: 42, name: "Cherrytomaten" },
            ])
          )
        }
        if (url === "/api/recipes") {
          return Promise.resolve(
            mockFetchResponse({ id: 42, title: "Test" }, { status: 201 })
          )
        }
        return Promise.resolve(mockFetchResponse([]))
      })

    const user = userEvent.setup()
    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://example.com/test")
    )

    await screen.findByText(/importiert von example\.com/i)

    // Row is locked, click ↻ to override
    await user.click(screen.getByRole("button", { name: /zutat ändern/i }))

    // Dropdown appears, pick a different ingredient
    const listbox = await screen.findByRole("listbox")
    const cherryOption = Array.from(
      listbox.querySelectorAll('[role="option"]')
    ).find((o) => o.textContent?.includes("Cherrytomaten"))
    expect(cherryOption).toBeDefined()
    await user.click(cherryOption!)

    await user.type(screen.getByLabelText(/zubereitung/i), "Kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    await waitFor(() => {
      expect(screen.getByText("recipe-detail-stub")).toBeInTheDocument()
    })

    const recipeCall = fetchSpy.mock.calls.find(
      ([u]) => u === "/api/recipes"
    ) as [string, RequestInit]
    const body = JSON.parse(recipeCall[1].body as string)
    expect(body.learned_aliases).toEqual([
      { alias_name: "Tomaten", ingredient_id: 42 },
    ])
  })

  it("sends empty learned_aliases when all rows are exact match (confidence 1.0) left alone", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const url =
          typeof input === "string" ? input : (input as Request).url
        if (url === "/api/tags") {
          return Promise.resolve(mockFetchResponse([]))
        }
        if (url === "/api/recipes/import") {
          return Promise.resolve(
            mockFetchResponse({
              title: "Test",
              instructions: "Mix.",
              image_url: null,
              servings: 2,
              source_url: "https://example.com/test",
              source_domain: "example.com",
              is_partial: false,
              existing_recipe_id: null,
              ingredients: [
                {
                  raw: "Tomaten",
                  name: "Tomaten",
                  quantity: 500,
                  unit: "g",
                  ingredient_id: 7,
                  confidence: 1.0,
                },
                {
                  raw: "Zwiebeln",
                  name: "Zwiebeln",
                  quantity: 2,
                  unit: "Stück",
                  ingredient_id: 8,
                  confidence: 1.0,
                },
              ],
            })
          )
        }
        if (url === "/api/recipes") {
          return Promise.resolve(
            mockFetchResponse({ id: 42, title: "Test" }, { status: 201 })
          )
        }
        return Promise.resolve(mockFetchResponse([]))
      })

    const user = userEvent.setup()
    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://example.com/test")
    )

    await screen.findByText(/importiert von example\.com/i)

    await user.type(screen.getByLabelText(/zubereitung/i), "Kochen.")
    await user.click(screen.getByRole("button", { name: /speichern/i }))

    await waitFor(() => {
      expect(screen.getByText("recipe-detail-stub")).toBeInTheDocument()
    })

    const recipeCall = fetchSpy.mock.calls.find(
      ([u]) => u === "/api/recipes"
    ) as [string, RequestInit]
    const body = JSON.parse(recipeCall[1].body as string)
    expect(body.learned_aliases).toEqual([])
  })

  it("renders an amber 'Teilimport' banner when is_partial is true", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : (input as Request).url
      if (url === "/api/tags") {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url === "/api/recipes/import") {
        return Promise.resolve(
          mockFetchResponse({
            title: "Spaghetti Bolognese",
            ingredients: [],
            instructions: "",
            image_url: "https://example.com/img.jpg",
            servings: 4,
            source_url: "https://unknown.example/recipe",
            source_domain: "unknown.example",
            is_partial: true,
          })
        )
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    renderForm(
      "/recipes/new?url=" + encodeURIComponent("https://unknown.example/recipe")
    )

    // Partial banner renders with amber styling
    await screen.findByText(/teilimport — bitte vervollständigen/i)
    expect(
      screen.getByText(/bitte zutaten und zubereitung ergänzen/i)
    ).toBeInTheDocument()

    // Existing "Importiert von" banner is NOT shown
    expect(
      screen.queryByText(/importiert von unknown\.example/i)
    ).not.toBeInTheDocument()

    // Basic fields are pre-filled from whatever the partial extraction salvaged
    expect(
      (screen.getByLabelText(/titel/i) as HTMLInputElement).value
    ).toBe("Spaghetti Bolognese")
    expect(
      (screen.getByLabelText(/bild-?url|bild/i) as HTMLInputElement).value
    ).toBe("https://example.com/img.jpg")

    // Instructions are empty (partial extraction didn't get them)
    expect(
      (screen.getByLabelText(/zubereitung/i) as HTMLTextAreaElement).value
    ).toBe("")

    // Speichern is still disabled (title is filled but instructions are empty)
    expect(
      screen.getByRole("button", { name: /speichern/i })
    ).toBeDisabled()

    // Verwerfen button present and functional
    expect(
      screen.getByRole("button", { name: /verwerfen/i })
    ).toBeInTheDocument()
  })
})

describe("RecipeListPage URL import", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("shows a URL import form next to 'Neues Rezept' and navigates with ?url=… on submit", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : (input as Request).url
      if (url.includes("/api/tags")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      if (url.includes("/api/recipes")) {
        return Promise.resolve(mockFetchResponse([]))
      }
      return Promise.resolve(mockFetchResponse([]))
    })

    const user = userEvent.setup()
    renderListInShell()

    const newButton = await screen.findByRole("link", {
      name: /neues rezept/i,
    })
    expect(newButton).toHaveAttribute("href", "/recipes/new")

    const urlInput = screen.getByPlaceholderText(/aus url importieren|url importieren/i)
    await user.type(urlInput, "https://www.fooby.ch/recipe")
    await user.click(screen.getByRole("button", { name: /importieren/i }))

    await waitFor(() => {
      expect(screen.getByText("recipe-form-stub")).toBeInTheDocument()
    })
    expect(screen.getByText("recipe-form-stub")).toHaveAttribute(
      "data-search",
      expect.stringContaining("url=")
    )
  })
})
