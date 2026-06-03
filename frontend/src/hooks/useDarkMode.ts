import { useState, useEffect, useCallback } from "react"

const THEME_KEY = "theme"
const DARK_CLASS = "dark"
const COLOR_SCHEME_QUERY = "(prefers-color-scheme: dark)"

function resolveIsDark(): boolean {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored === "dark") return true
  if (stored === "light") return false
  return window.matchMedia(COLOR_SCHEME_QUERY).matches
}

function applyTheme(isDark: boolean): void {
  document.documentElement.classList.toggle(DARK_CLASS, isDark)
}

export function useDarkMode() {
  const [isDark, setIsDark] = useState<boolean>(resolveIsDark)

  useEffect(() => {
    applyTheme(isDark)
  }, [isDark])

  const toggle = useCallback(() => {
    setIsDark((prev) => {
      const next = !prev
      localStorage.setItem(THEME_KEY, next ? "dark" : "light")
      return next
    })
  }, [])

  return { isDark, toggle }
}
