# 0001 — App shell, sidebar nav, and the no-collapse decision

**Status**: Accepted

## Context

Chuchiplaner shipped as a stack of full-screen pages with no persistent navigation. The HomePage was itself a button grid serving as the only nav. On mobile, switching sections meant leaving the kitchen context for the dashboard. The base-nova theme in `index.css` already defined the full sidebar CSS variable set, but no component consumed it.

A self-hosted family meal planner that is used in the kitchen — often one-handed on a phone — needs a proper app shell: persistent nav on desktop, a drawer on mobile, a visible page identity, and a dark mode that respects the time of day.

## Decision

1. Add an `AppLayout` that wraps every authenticated route with a `SidebarProvider` and renders the active page via `<Outlet />`.
2. Use the shadcn `sidebar` block (already a project dependency) for the underlying primitives. The generated `sidebar.tsx` is trimmed: drop `SidebarRail`, `SidebarInset`, `SidebarInput`, and the default `Cmd/Ctrl+B` keyboard shortcut.
3. Split the route tree in `App.tsx` into two branches:
   - Public routes: `/login`, `/register`, `/grocery-list/share/:token`, `/plan/:slug/:year/kw:week` — no shell.
   - Protected routes: `/`, `/plan`, `/grocery-list`, `/recipes`, `/recipes/:id`, `/inventory`, `/settings` — wrapped in `<AppLayout>` + `<ProtectedRoute>`, content via `<Outlet />`.
4. Make the home route (`/`) a `<Navigate to="/plan" replace />` redirect. The previous `HomePage` button grid is deleted.
5. **Do not expose a sidebar collapse toggle.** The sidebar is always expanded. The shadcn `SidebarRail` and the `Cmd/Ctrl+B` shortcut are trimmed from the generated block.
6. **Desktop sidebar is `position: fixed`, not scrollable.** The `SidebarProvider` wrapper uses `h-svh` to lock the viewport. The main content wrapper uses `min-h-0 overflow-hidden` to constrain its children, and the `<main>` element is the scroll container (`flex-1 overflow-auto`). The sidebar uses `fixed inset-y-0` with a gap div to reserve horizontal space in the flex layout. This means the sidebar never scrolls out of view, even on tall pages.
7. Mobile uses a `Sheet` driven by a topbar hamburger, auto-closing on route change.
8. Each page declares its title via a `<PageHeader title="..." />` component. No central route-handle / path-map registry.
9. Add a dark-mode toggle in the sidebar footer backed by a `useDarkMode` hook. The hook reads/writes `localStorage` under the key `"theme"`, falls back to `matchMedia('(prefers-color-scheme: dark)')`, and toggles `.dark` on `<html>`. Apply a no-flash inline `<script>` in `index.html` that reads the same `localStorage` key and applies the class before React mounts.
10. The `localStorage` key string (`"theme"`) is duplicated in two places — the inline no-flash script and the `useDarkMode` hook. Treat the key as a contract: if either side changes it, the other must change in lockstep.

## Consequences

**Positive**

- A real, discoverable app shell. Mobile users can switch sections one-handed.
- Dark mode works end-to-end (no first-paint flash).
- The base-nova theme is finally consumed.
- Each protected page is one `<PageHeader>` import away from being a "real" page; the pattern scales to new sections.

**Negative**

- The shadcn sidebar block ships with a collapse behavior we deliberately don't expose. Future contributors may be tempted to re-enable it. This ADR is the answer to "why don't we have collapse?".
- The inline `<script>` in `index.html` is brittle to rename: the `localStorage` key is duplicated between the script and the hook. Both must agree on the key.
- The five nav items, always-visible, take up horizontal space on narrow desktop windows. Acceptable because the week plan grid benefits from the wider viewport anyway.

**Reversibility**

- The route split is easy to revert (one branch in `App.tsx`).
- The decision to not collapse is a UX commitment, not a code commitment — adding collapse later is additive, not a rewrite.
- Dark mode plumbing is additive; removing it touches the layout, the hook, and the inline script, but no domain data is at risk.

## Alternatives considered

- **Top nav bar only** — rejected because the base-nova theme is sidebar-first and the kitchen use case needs mobile drawer support anyway.
- **Bottom tabs on mobile** — rejected because they eat vertical space on the recipe list and the week plan grid.
- **Keep HomePage as a real dashboard** — rejected as scope creep. The redirect is sufficient until there is something meaningful to dashboard.
- **Centralized path → title map** — rejected in favor of `<PageHeader>` per page. Explicit > magical for a five-route app.
- **An avatar menu hiding settings and logout** — rejected. With five items, all of them deserve a permanent home. Username + sign-out live in the sidebar footer.
- **Map the sidebar to a user-togglable collapse mode** — rejected. The five items all fit at full width; adding collapse adds UI complexity, a keyboard shortcut, and a persisted preference to manage, with no commensurate benefit.
