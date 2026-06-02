import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"

function App() {
  const { t } = useTranslation()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background text-foreground">
      <h1 className="text-4xl font-bold">{t("app.title")}</h1>
      <p className="text-lg text-muted-foreground">{t("app.welcome")}</p>
      <Button>Loslegen</Button>
    </div>
  )
}

export default App
