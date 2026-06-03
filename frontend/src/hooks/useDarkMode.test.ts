import { describe, it, expect, beforeEach, vi } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useDarkMode } from "./useDarkMode"

function setMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }))
}

describe("useDarkMode", () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove("dark")
  })

  it("resolves dark when localStorage.theme is 'dark'", () => {
    localStorage.setItem("theme", "dark")

    const { result } = renderHook(() => useDarkMode())

    expect(result.current.isDark).toBe(true)
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("resolves light when localStorage.theme is 'light'", () => {
    localStorage.setItem("theme", "light")

    const { result } = renderHook(() => useDarkMode())

    expect(result.current.isDark).toBe(false)
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("falls back to dark when localStorage is empty and system prefers dark", () => {
    setMatchMedia(true)

    const { result } = renderHook(() => useDarkMode())

    expect(result.current.isDark).toBe(true)
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("falls back to light when localStorage is empty and system prefers light", () => {
    setMatchMedia(false)

    const { result } = renderHook(() => useDarkMode())

    expect(result.current.isDark).toBe(false)
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("toggle flips class, writes localStorage, and returns new isDark", () => {
    localStorage.setItem("theme", "light")

    const { result } = renderHook(() => useDarkMode())

    act(() => {
      result.current.toggle()
    })

    expect(result.current.isDark).toBe(true)
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    expect(localStorage.getItem("theme")).toBe("dark")

    act(() => {
      result.current.toggle()
    })

    expect(result.current.isDark).toBe(false)
    expect(document.documentElement.classList.contains("dark")).toBe(false)
    expect(localStorage.getItem("theme")).toBe("light")
  })

  it("applies .dark class on documentElement based on resolved state", () => {
    localStorage.setItem("theme", "dark")

    renderHook(() => useDarkMode())

    expect(document.documentElement.classList.contains("dark")).toBe(true)

    // Clean and test light
    document.documentElement.classList.remove("dark")
    localStorage.setItem("theme", "light")

    renderHook(() => useDarkMode())

    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })
})
