import { useEffect, type ReactNode } from "react"

import { usePageHeaderContext } from "./PageHeaderContext"

interface PageHeaderProps {
  title: string
  actions?: ReactNode
  subtitle?: string
}

export function PageHeader({ title, actions, subtitle }: PageHeaderProps) {
  const { setValue } = usePageHeaderContext()

  useEffect(() => {
    setValue({ title, actions, subtitle })
    return () => setValue(null)
  }, [setValue, title, actions, subtitle])

  return null
}
