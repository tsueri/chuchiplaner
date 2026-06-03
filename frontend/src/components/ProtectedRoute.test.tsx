import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { ProtectedRoute } from "./ProtectedRoute"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"

function renderWithAuth(state: {
  user: AuthContextType["user"]
  loading: boolean
}) {
  const authValue: AuthContextType = {
    user: state.user,
    loading: state.loading,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  }
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={["/protected"]}>
        <Routes>
          <Route path="/login" element={<div>login-page</div>} />
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>protected-content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  )
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it("renders children when the user is authenticated", () => {
    renderWithAuth({
      user: { id: 1, username: "alice", role: "admin", household_id: 1 },
      loading: false,
    })

    expect(screen.getByText("protected-content")).toBeInTheDocument()
    expect(screen.queryByText("login-page")).not.toBeInTheDocument()
  })

  it("redirects to /login when there is no user", () => {
    renderWithAuth({ user: null, loading: false })

    expect(screen.getByText("login-page")).toBeInTheDocument()
    expect(screen.queryByText("protected-content")).not.toBeInTheDocument()
  })

  it("renders an inline loading indicator (not full-screen) when loading", () => {
    renderWithAuth({ user: null, loading: true })

    const loading = screen.getByText("Laden...")
    expect(loading).toBeInTheDocument()
    // The loading state must not stretch to fill the viewport — it must
    // render inside the shell's <main>, not replace it.
    expect(loading.closest("div.min-h-screen")).toBeNull()
  })
})
