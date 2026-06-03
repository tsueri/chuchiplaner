import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import App from "./App"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"

function renderApp(
  { user, path }: {
    user: AuthContextType["user"]
    path: string
  }
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
        <App />
      </MemoryRouter>
    </AuthContext.Provider>
  )
}

describe("App routing", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("redirects / to /plan with no history entry", () => {
    renderApp({
      user: { id: 1, username: "alice", role: "admin", household_id: 1 },
      path: "/",
    })

    // The / route is a Navigate to /plan, which is a protected route
    // wrapped in the shell. Confirm the shell rendered (= redirect
    // landed us on a protected route) and the old HomePage nav buttons
    // are gone.
    expect(screen.getByText("Chuchiplaner")).toBeInTheDocument()
    expect(screen.queryByText("Abmelden")).toBeInTheDocument()
  })

  it("renders the public /login route without the shell", () => {
    renderApp({ user: null, path: "/login" })

    // The shell renders "Chuchiplaner" in the sidebar header. Public routes
    // must NOT render the shell, so the brand must be absent.
    expect(screen.queryByText("Chuchiplaner")).toBeNull()
  })

  it("renders the public /register route without the shell", () => {
    renderApp({ user: null, path: "/register" })

    expect(screen.queryByText("Chuchiplaner")).toBeNull()
  })

  it("renders the public shared grocery list without the shell", () => {
    renderApp({ user: null, path: "/grocery-list/share/abc123" })

    expect(screen.queryByText("Chuchiplaner")).toBeNull()
  })

  it("renders the public week plan without the shell", () => {
    renderApp({
      user: null,
      path: "/plan/my-house/2026/kw25",
    })

    expect(screen.queryByText("Chuchiplaner")).toBeNull()
  })

  it("redirects an unauthenticated user from a protected route to /login", () => {
    renderApp({ user: null, path: "/plan" })

    // /login renders the username field labelled "Benutzername".
    expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument()
  })

  it("does not render the /__shell-preview demo route", () => {
    renderApp({
      user: { id: 1, username: "alice", role: "admin", household_id: 1 },
      path: "/__shell-preview",
    })

    // The demo content from slice #20 must be gone.
    expect(screen.queryByText(/Shell Preview/i)).toBeNull()
  })
})
