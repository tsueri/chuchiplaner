import { Menu, Moon, Sun } from "lucide-react"
import { useEffect } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { useAuth } from "@/contexts/useAuth"
import { useDarkMode } from "@/hooks/useDarkMode"

import { PageHeaderProvider, usePageHeaderContext } from "./PageHeaderContext"
import { SidebarNav } from "./SidebarNav"
import { Button } from "@/components/ui/button"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarProvider,
  useSidebar,
} from "@/components/ui/sidebar"

function MobileSheetCloseOnRouteChange() {
  const { setOpenMobile } = useSidebar()
  const location = useLocation()

  useEffect(() => {
    setOpenMobile(false)
  }, [location.pathname, setOpenMobile])

  return null
}

function MobileHamburger() {
  const { toggleSidebar, isMobile } = useSidebar()

  if (!isMobile) return null

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      className="md:hidden"
      onClick={toggleSidebar}
      aria-label="Navigation öffnen"
    >
      <Menu />
    </Button>
  )
}

function Topbar() {
  const { value } = usePageHeaderContext()
  const title = value?.title ?? ""

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background px-4 md:px-6">
      <MobileHamburger />
      <div className="flex min-w-0 flex-1 flex-col justify-center">
        <h1 className="font-heading truncate text-lg font-semibold leading-none tracking-tight text-foreground">
          {title}
        </h1>
        {value?.subtitle && (
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {value.subtitle}
          </p>
        )}
      </div>
      {value?.actions && (
        <div className="flex items-center gap-2">{value.actions}</div>
      )}
    </header>
  )
}

function SidebarFooterBlock() {
  const { user, logout } = useAuth()
  const { isDark, toggle } = useDarkMode()

  return (
    <SidebarFooter>
      <div className="flex flex-col gap-1 px-2 pt-1">
        <span className="truncate text-xs text-muted-foreground">
          {user?.username ?? ""}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="flex-1 justify-start"
            onClick={toggle}
            aria-label={isDark ? "Light mode aktivieren" : "Dark mode aktivieren"}
          >
            {isDark ? <Sun /> : <Moon />}
            <span>{isDark ? "Light mode" : "Dark mode"}</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              void logout()
            }}
          >
            Abmelden
          </Button>
        </div>
      </div>
    </SidebarFooter>
  )
}

function SidebarShell() {
  return (
    <Sidebar collapsible="none" className="border-r border-sidebar-border">
      <SidebarHeader className="px-3 py-3">
        <span className="font-heading text-base font-semibold tracking-tight">
          Chuchiplaner
        </span>
      </SidebarHeader>
      <SidebarContent>
        <SidebarNav />
      </SidebarContent>
      <SidebarFooterBlock />
    </Sidebar>
  )
}

export function AppLayout() {
  return (
    <PageHeaderProvider>
      <SidebarProvider>
        <MobileSheetCloseOnRouteChange />
        <SidebarShell />
        <div className="flex flex-1 flex-col min-h-0 overflow-hidden">
          <Topbar />
          <main className="flex-1 overflow-auto p-6 md:p-8">
            <Outlet />
          </main>
        </div>
      </SidebarProvider>
    </PageHeaderProvider>
  )
}
