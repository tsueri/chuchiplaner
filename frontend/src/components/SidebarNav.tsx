import {
  CalendarDays,
  Refrigerator,
  Settings,
  ShoppingCart,
  UtensilsCrossed,
} from "lucide-react"
import { NavLink, useLocation } from "react-router-dom"

import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

const NAV_ITEMS = [
  { to: "/plan", label: "Wochenplan", Icon: CalendarDays },
  { to: "/grocery-list", label: "Einkaufsliste", Icon: ShoppingCart },
  { to: "/recipes", label: "Rezepte", Icon: UtensilsCrossed },
  { to: "/inventory", label: "Vorrat", Icon: Refrigerator },
  { to: "/settings", label: "Einstellungen", Icon: Settings },
] as const

function isItemActive(pathname: string, to: string): boolean {
  if (to === "/recipes") {
    return pathname === "/recipes" || pathname.startsWith("/recipes/")
  }
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function SidebarNav() {
  const { pathname } = useLocation()

  return (
    <SidebarMenu>
      {NAV_ITEMS.map(({ to, label, Icon }) => (
        <SidebarMenuItem key={to}>
          <SidebarMenuButton
            isActive={isItemActive(pathname, to)}
            render={<NavLink to={to} />}
          >
            <Icon />
            <span>{label}</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  )
}
