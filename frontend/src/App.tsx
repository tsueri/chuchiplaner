import { Navigate, Outlet, Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/AppLayout"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import GroceryListPage from "@/pages/GroceryListPage"
import GroceryListSharePage from "@/pages/GroceryListSharePage"
import IngredientsPage from "@/pages/IngredientsPage"
import InventoryPage from "@/pages/InventoryPage"
import LoginPage from "@/pages/LoginPage"
import PublicPlanPage from "@/pages/PublicPlanPage"
import RecipeDetailPage from "@/pages/RecipeDetailPage"
import RecipeFormPage from "@/pages/RecipeFormPage"
import RecipeListPage from "@/pages/RecipeListPage"
import RegisterPage from "@/pages/RegisterPage"
import SettingsPage from "@/pages/SettingsPage"
import WeekPlanPage from "@/pages/WeekPlanPage"

function App() {
  return (
    <Routes>
      {/* Public branch — no shell. */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/grocery-list/share/:token"
        element={<GroceryListSharePage />}
      />
      <Route
        path="/plan/:slug/:year/:weekParam"
        element={<PublicPlanPage />}
      />

      {/* Protected branch — wrapped in AppLayout + ProtectedRoute. */}
      <Route element={<AppLayout />}>
        <Route
          element={
            <ProtectedRoute>
              <Outlet />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/plan" replace />} />
          <Route path="/plan" element={<WeekPlanPage />} />
          <Route path="/grocery-list" element={<GroceryListPage />} />
          <Route path="/recipes" element={<RecipeListPage />} />
          <Route path="/recipes/new" element={<RecipeFormPage />} />
          <Route path="/recipes/:id" element={<RecipeDetailPage />} />
          <Route path="/ingredients" element={<IngredientsPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
