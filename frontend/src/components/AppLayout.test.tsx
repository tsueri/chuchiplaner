import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { AppLayout } from "./AppLayout"
import { PageHeader } from "./PageHeader"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"

function renderInShell(
  ui: React.ReactNode,
  { user = null, path = "/" }: { user?: AuthContextType["user"]; path?: string } = {}
) {
  const authValue: AuthContextType = {
    user,
    loading: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  }
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="*" element={ui} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  )
}

describe("AppLayout", () => {
  it("shows the page title from PageHeader in the topbar", () => {
    renderInShell(
      <>
        <PageHeader title="Wochenplan" />
        <p>page body</p>
      </>
    )

    expect(screen.getByRole("heading", { level: 1, name: "Wochenplan" }))
      .toBeInTheDocument()
    expect(screen.getByText("page body")).toBeInTheDocument()
  })

  it("shows the page subtitle in the topbar", () => {
    renderInShell(
      <PageHeader title="Einkaufsliste" subtitle="3 von 5 offen" />
    )

    expect(screen.getByText("3 von 5 offen")).toBeInTheDocument()
  })

  it("renders page actions in the topbar", () => {
    renderInShell(
      <PageHeader
        title="Einkaufsliste"
        actions={<button>Aktion</button>}
      />
    )

    expect(screen.getByRole("button", { name: "Aktion" })).toBeInTheDocument()
  })

  it("renders the username in the sidebar footer when authenticated", () => {
    renderInShell(<PageHeader title="Vorrat" />, {
      user: { id: 1, username: "alice", role: "admin", household_id: 1 },
    })

    expect(screen.getByText("alice")).toBeInTheDocument()
  })
})
