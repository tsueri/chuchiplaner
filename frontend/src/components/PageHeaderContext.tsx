import { createContext, useContext, useState, type ReactNode } from "react"

interface PageHeaderValue {
  title: string
  subtitle?: string
  actions?: ReactNode
}

const PageHeaderContext = createContext<{
  value: PageHeaderValue | null
  setValue: (v: PageHeaderValue | null) => void
} | null>(null)

export function PageHeaderProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<PageHeaderValue | null>(null)
  return (
    <PageHeaderContext.Provider value={{ value, setValue }}>
      {children}
    </PageHeaderContext.Provider>
  )
}

export function usePageHeaderContext() {
  const ctx = useContext(PageHeaderContext)
  if (!ctx) {
    throw new Error(
      "usePageHeaderContext must be used within a PageHeaderProvider"
    )
  }
  return ctx
}
