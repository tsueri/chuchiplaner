import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { AppLayout } from "@/components/AppLayout"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import GroceryListPage from "./GroceryListPage"

function mockFetchResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

function buildFetchSpy() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = typeof input === "string" ? input : (input as Request).url
    if (url === "/api/grocery-list") {
      return Promise.resolve(
        mockFetchResponse({
          id: 1,
          household_id: 1,
          week_plan_id: null,
          share_token: null,
          created_at: null,
          completed_at: null,
          items: [],
        })
      )
    }
    if (url === "/api/weeks") {
      return Promise.resolve(mockFetchResponse([]))
    }
    return Promise.resolve(mockFetchResponse([]))
  })
}

function renderInShell(ui: React.ReactNode, initialEntries = ["/grocery-list"]) {
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
            <Route path="/grocery-list" element={ui} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  )
}

describe("GroceryListPage", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders the page with header 'Einkaufsliste'", async () => {
    buildFetchSpy()

    renderInShell(<GroceryListPage />)

    expect(
      await screen.findByRole("heading", { level: 1, name: "Einkaufsliste" })
    ).toBeInTheDocument()
  })

  it("includes 'Msp' in the unit dropdowns", async () => {
    const user = userEvent.setup()
    buildFetchSpy()

    renderInShell(<GroceryListPage />)

    await user.click(
      await screen.findByRole("button", { name: /extra artikel/i })
    )

    const selects = screen.getAllByRole("combobox")
    const unitSelect = selects.find(
      (s) => (s as HTMLSelectElement).value === "Stück"
    )
    expect(unitSelect).toBeDefined()

    const options = Array.from(
      (unitSelect as HTMLSelectElement).options
    ).map((o) => o.value)
    expect(options).toContain("Msp")
  })
})
