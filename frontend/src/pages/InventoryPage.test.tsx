import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { AppLayout } from "@/components/AppLayout"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"
import InventoryPage from "./InventoryPage"

function mockFetchResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

function buildFetchSpy(inventoryItems: unknown[] = [], ingredients: unknown[] = []) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = typeof input === "string" ? input : (input as Request).url
    if (url === "/api/inventory") {
      return Promise.resolve(mockFetchResponse(inventoryItems))
    }
    if (url.startsWith("/api/ingredients")) {
      return Promise.resolve(mockFetchResponse(ingredients))
    }
    return Promise.resolve(mockFetchResponse([]))
  })
}

function renderInShell(ui: React.ReactNode, initialEntries = ["/inventory"]) {
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
            <Route path="/inventory" element={ui} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  )
}

describe("InventoryPage", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders the page with header 'Vorrat'", async () => {
    buildFetchSpy()

    renderInShell(<InventoryPage />)

    expect(
      await screen.findByRole("heading", { level: 1, name: "Vorrat" })
    ).toBeInTheDocument()
  })

  it("includes 'Msp' in the unit dropdowns", async () => {
    const user = userEvent.setup()
    buildFetchSpy()

    renderInShell(<InventoryPage />)

    await user.click(await screen.findByRole("button", { name: /hinzufügen/i }))

    const selects = screen.getAllByRole("combobox")
    const unitSelect = selects.find((s) => (s as HTMLSelectElement).value === "g")
    expect(unitSelect).toBeDefined()

    const options = Array.from(
      (unitSelect as HTMLSelectElement).options
    ).map((o) => o.value)
    expect(options).toContain("Msp")
  })
})
