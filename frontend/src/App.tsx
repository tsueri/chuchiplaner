import { useTranslation } from "react-i18next"
import { Link, Route, Routes } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { useAuth } from "@/contexts/AuthContext"
import GroceryListPage from "@/pages/GroceryListPage"
import GroceryListSharePage from "@/pages/GroceryListSharePage"
import InventoryPage from "@/pages/InventoryPage"
import LoginPage from "@/pages/LoginPage"
import PublicPlanPage from "@/pages/PublicPlanPage"
import RecipeDetailPage from "@/pages/RecipeDetailPage"
import RecipeListPage from "@/pages/RecipeListPage"
import RegisterPage from "@/pages/RegisterPage"
import SettingsPage from "@/pages/SettingsPage"
import WeekPlanPage from "@/pages/WeekPlanPage"

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
          <Link to="/plan">
            <Button variant="outline">Wochenplan</Button>
          </Link>
          <Link to="/grocery-list">
            <Button variant="outline">Einkaufsliste</Button>
          </Link>
          <Link to="/recipes">
            <Button variant="outline">Rezepte</Button>
          </Link>
          <Link to="/inventory">
            <Button variant="outline">Vorrat</Button>
          </Link>
          <Link to="/settings">
            <Button variant="outline">Einstellungen</Button>
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
        path="/recipes"
        element={
          <ProtectedRoute>
            <RecipeListPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recipes/:id"
        element={
          <ProtectedRoute>
            <RecipeDetailPage />
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
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/plan"
        element={
          <ProtectedRoute>
            <WeekPlanPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/grocery-list"
        element={
          <ProtectedRoute>
            <GroceryListPage />
          </ProtectedRoute>
        }
      />
      <Route path="/grocery-list/share/:token" element={<GroceryListSharePage />} />
      <Route path="/plan/:slug/:year/kw:week" element={<PublicPlanPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
    </Routes>
  )
}

export default App
