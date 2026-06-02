import { useTranslation } from "react-i18next"
import { Link, Route, Routes } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { useAuth } from "@/contexts/AuthContext"
import InventoryPage from "@/pages/InventoryPage"
import LoginPage from "@/pages/LoginPage"
import RegisterPage from "@/pages/RegisterPage"

function HomePage() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background text-foreground">
      <h1 className="text-4xl font-bold">{t("app.title")}</h1>
      <p className="text-lg text-muted-foreground">
        {user
          ? `${t("app.welcome")}, ${user.username}!`
          : t("app.welcome")}
      </p>
      {user && (
        <div className="flex gap-2">
          <Link to="/inventory">
            <Button variant="outline">Vorrat</Button>
          </Link>
        </div>
      )}
      <div className="flex gap-2">
        {user ? (
          <Button onClick={logout}>Abmelden</Button>
        ) : (
          <>
            <Link to="/login">
              <Button>Anmelden</Button>
            </Link>
            <Link to="/register">
              <Button variant="outline">Registrieren</Button>
            </Link>
          </>
        )}
      </div>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/inventory"
        element={
          <ProtectedRoute>
            <InventoryPage />
          </ProtectedRoute>
        }
      />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
    </Routes>
  )
}

export default App
