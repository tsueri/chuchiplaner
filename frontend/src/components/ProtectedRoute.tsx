import { Navigate } from "react-router-dom"
import { useAuth } from "@/contexts/useAuth"

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="p-4 text-muted-foreground">Laden...</div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
