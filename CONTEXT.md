# Chuchiplaner

A self-hosted family meal planner for Swiss households. Reduces food waste by planning weekly menus based on available fridge ingredients.

## Stack

- **Backend**: Python 3.12+ / FastAPI / SQLAlchemy 2.0 (async) / SQLite (WAL mode) / Alembic
- **Frontend**: React 19 / TypeScript / shadcn/ui (base-nova) / Tailwind CSS 4 / Vite
- **Deployment**: Docker Compose (single container via multi-stage build, daily backup sidecar)

## Domain Glossary

| Term | Definition |
|---|---|
| **Ingredient** | A canonical food item in the global catalog (e.g. "Pouletbrust"). Shared across all households. |
| **IngredientAlias** | A per-household mapping from a scraped ingredient name (e.g. "Hähnchenbrust") to a canonical Ingredient. Learned when users confirm matches during recipe import. Uniqueness is enforced by a DB index on `(household_id, lower(alias_name))`; conflicting writes return 409. Aliases are persisted only for rows the user *actively confirmed or changed* during the import flow — not for every row the form touched — to keep the alias table small. |
| **Recipe** | A meal imported from a Swiss cooking site or created manually. Contains title, instructions, image_url, source_url, source_domain, servings (default 4), and a list of RecipeIngredients (ingredient + quantity + unit + order_index). Soft-deleted via `deleted_at`. `(household_id, source_url)` is unique among non-deleted rows — re-saving the same URL returns 409 with the existing recipe's id. |
| **RecipeTag** | A tag attached to a Recipe. Tags have a `group`: `"season"` (fixed: Frühling/Sommer/Herbst/Winter/Ganzjährig) or `"ingredient"` (free-form per household). |
| **RecipeFavorite** | Per-user bookmark on a Recipe. |
| **RecipeNote** | Per-user note on a Recipe. Visibility: `"private"` or `"household"`. |
| **InventoryItem** | A food item in the household inventory. Fields: ingredient_id, quantity, unit, expiry_date (optional), category (`raw`/`cooked`/`frozen`). cooked items can have source_recipe_id and source_week_plan_id (from the cooking workflow). |
| **Household** | A named group of users. Has a unique `slug` (for public plan URLs), an `invite_code`, `default_size` (persons), and `default_public` (default week visibility). |
| **User** | A member of a household. Role: `"admin"` or `"member"`. Admins manage the household; members manage recipes/plans/inventory. |
| **Session** | Server-side token (64-char hex) stored as an httponly cookie. Expires after 7 days. |
| **WeekPlan** | A weekly meal plan for a household, uniquely identified by `(household_id, year, iso_week)`. Contains 28 MealSlots (7 days × 4 meal types). |
| **MealSlot** | A single meal position in a WeekPlan. Fields: day_of_week (0=Mon..6=Sun), meal_type (`breakfast`/`lunch`/`dinner`/`dessert`), active (bool), recipe_id (nullable), portions, dietary_filter_tag_id, cooked (bool). |
| **MealSlotTemplate** | A household-level default configuration for which slots are active per day/meal_type, plus default_portions. Used when creating new WeekPlans. |
| **GroceryList** | Generated shopping list for a week's plan. Items are aggregated recipe ingredients minus inventory. Can be shared via a unique `share_token`. |
| **GroceryListItem** | A single line in the grocery list. Has quantity, unit, checked (bool), and an optional `recipe_breakdown` (JSON) showing per-recipe sources. |
| **MatchingEngine** | Core algorithm that scores recipes against available inventory. Returns `ScoredRecipe` objects sorted by match percentage + urgency boost (ingredients expiring within 3 days get +0.1). Three modes: `exact` (all ingredients available), `partial` (any match), `ingredient_first` (filter by specific ingredient). |
| **UnitConverter** | Static utility that normalizes ingredient quantities to canonical units. Input: (amount, unit_str). Output: (grams, milliliters, pieces) — exactly one non-None. Supports g, kg, ml, l, EL (15ml), TL (5ml), Stück, Bund, Prise. |
| **IngredientLineParser** | Splits a raw scraped ingredient string (e.g. `"600g Kalbfleisch"`, `"1 Zwiebel, gehackt"`) into `(quantity, unit, name)`. Returns `quantity=None, unit=None, name=line` for unparseable lines (e.g. `"Salz und Pfeffer"`). Uses the source-side unit vocabulary — canonical synonyms (Esslöffel, Teelöffel, Dose, Becher, …) plus the standard `UnitConverter` set — and is the only module that knows those synonyms. Unit name maps to the canonical form (`"EL"` not `"Esslöffel"`). Ranges (`"2-3 EL"`) collapse to the lower bound. |
| **IngredientNormalizer** | Resolves parsed ingredient names to canonical Ingredient IDs. Uses household aliases first, then exact name match, then fuzzy matching (SequenceMatcher, threshold 0.6). Returns `(ingredient_id, confidence)` where 1.0 means exact/alias. Wired into the import pipeline: `POST /api/recipes/import` runs the parser + normalizer for every scraped line and returns one `ScrapedIngredientItem` per line. |
| **ScrapedIngredientItem** | Per-scraped-line payload inside the import response. Fields: `raw` (original string), `name` (parsed), `quantity` (float or null), `unit` (canonical form or null), `ingredient_id` (matched canonical or null), `confidence` (0.0–1.0). The form pre-fills one row per item, locking rows at confidence 1.0, pre-selecting the suggestion at 0.6–1.0, and leaving rows open at < 0.6. |
| **ScrapedRecipe.is_partial** | Boolean flag on the import response. `True` means the full recipe-scrapers library failed and the scraper fell back to best-effort extraction (title from `<title>`, image from `og:image`); the user must fill the rest by hand. `False` means a structured recipe was extracted. The 422 "could not extract" case is reserved for `is_partial=False` AND no data was found at all. |

## Architecture

```
browser ──▶ Vite dev proxy (5173) ──▶ FastAPI (8000) ──▶ SQLite (WAL)
                │                          │
                ▼                          ▼
         React SPA (build)          Alembic migrations
```

**Backend** (`backend/`): FastAPI app factory (`create_app()` in `app/main.py`). Middleware: CORS + custom SessionMiddleware (extracts `session_token` cookie → `request.state.session_token`). Routers mounted under `/api/`. Serves React static build from `static/` in production.

**Frontend** (`frontend/`): React SPA with react-router-dom v7. Cookie-based auth via AuthContext (React Context). No centralized API client — each page defines its own `async function api()`. No shared state between pages. Protected routes wrapped in `ProtectedRoute` (redirects to `/login`). Every protected page renders inside `AppLayout` (persistent sidebar on `md+`, mobile `Sheet` on `<md`, topbar with page title + mobile hamburger) and declares its topbar title via `<PageHeader>`.

**Auth flow**: bcrypt-hashed passwords, server-side sessions in `sessions` table, httponly `session_token` cookie. `get_current_user` dependency looks up session, validates token + expiry, eager-loads user + household.

**Drag-and-drop**: Native HTML5 drag-and-drop (no library). Recipe suggestion cards are draggable; meal slot cells are drop targets. `PUT /api/weeks/:year/:week/slots` bulk-updates slots on drop.

**i18n**: react-i18next with `i18next-parser` for extraction. Currently one locale (`de`), minimally used — most strings are hardcoded German.

**Search**: FTS5 virtual table (`recipes_fts`) on recipe title + instructions. Populated on create/update via raw SQL. Full-text query with LIKE fallback.

**Backup**: Docker sidecar (`backup/`) copies the SQLite file daily with 7-day retention. Manual JSON export button in settings (`GET /api/household/export`).

## Backend Map

```
backend/
├── app/
│   ├── main.py              # create_app() factory: CORS, SessionMiddleware, routers, static files
│   ├── api/                 # Route handlers (one file per feature)
│   │   ├── auth.py          # register, login, logout, me, password, get_current_user dependency
│   │   ├── recipes.py       # CRUD, import (scrape URL), favorites, notes, tags, FTS search
│   │   ├── weeks.py         # get/create plan, update slots, cook, leftovers, visibility
│   │   ├── inventory.py     # CRUD for household inventory
│   │   ├── ingredients.py   # CRUD for global ingredient catalog
│   │   ├── matching.py      # POST /api/match — calls MatchingEngine with inventory + recipes
│   │   ├── grocery_list.py  # generate, regenerate, complete, share
│   │   ├── household.py     # CRUD, invite codes, meal templates, aliases, export
│   │   ├── public_plan.py   # GET /api/public/plan/:slug/:year/:week (no auth)
│   │   └── health.py        # Health check
│   ├── core/
│   │   ├── config.py        # Pydantic BaseSettings (CHUCHI_ env prefix)
│   │   └── middleware.py    # SessionMiddleware — reads session_token cookie
│   ├── db/
│   │   ├── base.py          # SQLAlchemy DeclarativeBase
│   │   └── session.py       # Async engine, session factory, get_db dependency. WAL + foreign_keys pragmas.
│   ├── models/              # SQLAlchemy ORM models (one file per entity group)
│   │   ├── user.py          # User, Session
│   │   ├── household.py     # Household, MealSlotTemplate
│   │   ├── ingredient.py    # Ingredient, IngredientAlias
│   │   ├── recipe.py        # Recipe, RecipeIngredient, RecipeTag, Tag, RecipeFavorite, RecipeNote
│   │   ├── inventory.py     # InventoryItem
│   │   ├── week_plan.py     # WeekPlan, MealSlot
│   │   └── grocery_list.py  # GroceryList, GroceryListItem
│   ├── schemas/             # Pydantic request/response models (one file per feature). All use from_attributes=True.
│   └── services/            # Business logic layer
│       ├── auth.py          # Password hashing (bcrypt/passlib), user/session CRUD
│       ├── household.py     # Household CRUD, invite codes, meal templates
│       ├── week_plan.py     # ISO week helpers, plan creation (optionally copy from previous), slot management, reservation computation
│       ├── grocery_list.py  # List generation (aggregate + subtract inventory), completion (transfer to inventory)
│       ├── matching_engine.py  # Pure function: suggest(inventory, recipes, mode, ...) → sorted ScoredRecipe[]
│       ├── scraper.py       # RecipeScraper: recipe-scrapers lib, in-memory cache, 2s rate limit, threading.Lock
│       ├── unit_converter.py   # Static class: normalize(amount, unit) → (grams, ml, pieces)
│       └── normalizer.py       # IngredientNormalizer: resolve(name, aliases) → (id, confidence), learn_alias()
├── alembic/                 # 13 migrations (builds full schema incrementally)
└── tests/                   # pytest + pytest-asyncio, in-memory SQLite, HTTP test client per feature
```

## Frontend Map

```
frontend/src/
├── main.tsx                  # React entry: BrowserRouter, AuthProvider, App
├── App.tsx                   # Routes: public branch (no shell) + protected branch (AppLayout + ProtectedRoute + Outlet). `/` redirects to `/plan`.
├── index.css                 # Tailwind 4 + shadcn + Geist font + theme (OKLCH vars, light/dark)
├── contexts/
│   └── AuthContext.tsx        # Auth state: user, loading, login(), register(), logout(). Calls /api/auth/me on mount.
├── components/
│   ├── AppLayout.tsx            # App-level shell: SidebarProvider, persistent Sidebar on md+, mobile Sheet on <md, topbar (page title + mobile hamburger), sidebar footer (username + sign-out + dark-mode toggle), renders active route via <Outlet />. Subscribes to useLocation to close the mobile sheet on route change.
│   ├── PageHeader.tsx           # Per-page topbar title + optional right-aligned actions + optional subtitle. Used by every protected page.
│   ├── SidebarNav.tsx           # The five NavLink items with lucide icons (CalendarDays, ShoppingCart, UtensilsCrossed, Refrigerator, Settings). Encapsulates the item list so AppLayout does not know the labels or icons.
│   ├── ProtectedRoute.tsx       # Loading spinner → redirect to /login if no user
│   └── ui/
│       └── button.tsx           # shadcn Button (on @base-ui/react/button), CVA variants
├── hooks/
│   └── useDarkMode.ts           # { isDark, toggle }. Reads/writes localStorage["theme"], falls back to matchMedia('(prefers-color-scheme: dark)'), toggles .dark on <html>. The same localStorage key is read by the no-flash inline <script> in index.html — see ADR 0001.
├── pages/
│   ├── LoginPage.tsx          # Username + password form
│   ├── RegisterPage.tsx       # Username + password + optional invite code (from ?invite_code= query param)
│   ├── RecipeListPage.tsx     # Search input, favorites toggle, tag filter pills, grid of recipe cards. Topbar actions: a small "Aus URL importieren…" input + Importieren button (navigates to /recipes/new?url=…) and a primary "Neues Rezept" link.
│   ├── RecipeFormPage.tsx     # Create-recipe form: basic fields + tag pills (fetched from /api/tags on mount, toggled locally) + dynamic ingredient rows (combobox with debounced /api/ingredients?q=…, quantity, unit, remove). Clicking a result locks the row; empty rows dropped on submit. Submit is POST /api/recipes, then PUT /api/recipes/<id> { tag_ids } only if any tags are selected; PUT failure renders inline, recipe kept. URL import: when mounted with a `?url=` query param, calls POST /api/recipes/import on mount, prefills the six basic fields, and shows an "Importiert von <domain>" banner with a "Verwerfen" action that resets the form and strips the `url` query param. A non-2xx import response renders the detail message inline and leaves the form blank.
│   ├── RecipeDetailPage.tsx   # Full recipe view: ingredients, instructions, tags, notes CRUD, favorites, delete (admin)
│   ├── WeekPlanPage.tsx       # Split-pane: 7×4 meal grid (left) + suggestions panel (right). Drag-and-drop, cooking flow, public toggle
│   ├── GroceryListPage.tsx    # Aggregated list with check-off, inline edit, regenerate, share, complete
│   ├── GroceryListSharePage.tsx # Public read-only grocery list via share token (no auth)
│   ├── PublicPlanPage.tsx     # Public read-only week plan via slug (no auth)
│   ├── InventoryPage.tsx      # Add/edit/delete inventory items, filter/sort by category/expiry
│   └── SettingsPage.tsx       # Password change, household settings, meal template, invite code, members, export
└── i18n/
    └── locales/de/
        └── translation.json   # German translations (minimally used — most strings are hardcoded)
```

### Routing Table

| Path | Page | Protected |
|---|---|---|
| `/` | `<Navigate to="/plan" replace />` (no HomePage) | Yes |
| `/login` | LoginPage | No |
| `/register` | RegisterPage | No |
| `/recipes` | RecipeListPage | Yes |
| `/recipes/:id` | RecipeDetailPage | Yes |
| `/inventory` | InventoryPage | Yes |
| `/settings` | SettingsPage | Yes |
| `/plan` | WeekPlanPage | Yes |
| `/grocery-list` | GroceryListPage | Yes |
| `/grocery-list/share/:token` | GroceryListSharePage | No |
| `/plan/:slug/:year/kw:week` | PublicPlanPage | No |

## Key Conventions

### API client pattern
Every page defines its own `async function api(path, options?)` helper — a thin wrapper around `fetch(/api${path}, { credentials: "same-origin" })`. Throws on non-2xx with `detail` from the response body. 204 returns `null`.

### Cancel-based fetch pattern
Pages use a `let cancelled = false` flag in useEffect cleanup to avoid state updates on unmounted components:
```typescript
useEffect(() => {
  let cancelled = false
  async function load() {
    const data = await api("/some-endpoint")
    if (cancelled) return
    setData(data)
  }
  load()
  return () => { cancelled = true }
}, [])
```

### State management
No external state library. Auth state lives in React Context (`AuthContext`). All other state (data, loading, form inputs) is local `useState` + `useEffect` per page. Pages fetch independently — no shared data stores.

### App shell
Every protected route renders inside `AppLayout` (`components/AppLayout.tsx`). The shell owns the persistent `Sidebar` on `md+` and a mobile `Sheet` on `<md`, the topbar (page title + mobile hamburger), the dark-mode toggle, and the sidebar footer (username + sign-out). The active page's content is mounted via `<Outlet />` from react-router.

The route tree in `App.tsx` has two branches: public routes (`/login`, `/register`, `/grocery-list/share/:token`, `/plan/:slug/:year/kw:week`) render without the shell; protected routes are nested under `<AppLayout>` + `<ProtectedRoute>`. The `/` route is a `<Navigate to="/plan" replace />` redirect — there is no dashboard at `/`.

Each page declares its topbar title with `<PageHeader title="..." actions?={...} />`. The `actions` slot is the right place for page-level buttons (e.g. "Regenerate" on the grocery list). Page content sits inside `<main className="flex-1 p-6 md:p-8">` — no max-width container; the week plan grid fills the canvas.

The sidebar is always expanded; collapse is intentionally not exposed (see ADR 0001). Dark mode is plumbed through `useDarkMode` plus a no-flash inline `<script>` in `index.html`; the `localStorage` key (`"theme"`) is duplicated in both places and must stay in lockstep.

### ISO weeks
All week planning uses ISO 8601 week dates (Monday start), timezone Europe/Zurich. Helper functions in `app/services/week_plan.py`:
- `get_current_iso_week()` → (year, week)
- `iso_week_start_date(year, week)` → first Monday
- `iso_week_end_date(year, week)` → Sunday

A week is editable if it's the current week or up to 4 weeks ahead. Past weeks are read-only archive.

### Soft delete
Recipes use a `deleted_at` timestamp (nullable). All recipe queries filter `WHERE deleted_at IS NULL`. Hard delete is never performed on recipes — this preserves recipe references in historical week plans.

### Orphaned references
MealSlot's `recipe_id` is nullable. When a recipe is soft-deleted, slot references are NOT cleaned up — the plan still shows the recipe title but the detail link is dead. The frontend handles this with "Delete"-button check (`recipe_id` truthiness).

### FTS5 search
Full-text search uses a virtual `recipes_fts` table. Populated on recipe create/update via raw SQL in `recipes.py` (not SQLAlchemy ORM). The search endpoint falls back to `LIKE` when FTS returns no results.

### Scraper caching
Recipe URLs are cached in-memory for the lifetime of the process. A 2-second rate limit between requests protects the source sites. Blocking `time.sleep` (not async) — acceptable because the scrape endpoint is called manually, not in hot paths.

### Inventory reservations
When a recipe is planned but not yet cooked, its ingredients are reserved (scaled to slot portions). The MatchingEngine subtracts these reservations from available inventory so it doesn't suggest recipes that use already-committed ingredients. Reservations are computed on-the-fly by `compute_reservations()` in `week_plan.py`.

### Cooking workflow
1. User clicks "Gekocht" on a MealSlot → `POST /api/weeks/:year/:week/slots/:id/cook` → deducts scaled ingredient quantities from InventoryItems (reduces amounts, removes depleted items).
2. User optionally enters leftover portions → `POST /api/weeks/:year/:week/slots/:id/leftovers` → creates a new InventoryItem with category `cooked`, linked to source_recipe_id and source_week_plan_id.

### Grocery list generation
`get_or_generate_list()` in `grocery_list.py`:
1. Sum all ingredient needs from uncooked MealSlots (scaled to slot portions).
2. Subtract current inventory quantities (same unit dimension via UnitConverter).
3. Create GroceryListItems grouped by ingredient.
4. Attach `recipe_breakdown` JSON showing per-recipe contribution to each item.
5. `complete_list()` transfers unchecked items to inventory (adds to existing InventoryItem or creates new one).

## Testing

**Framework**: pytest + pytest-asyncio (mode: auto). In-memory SQLite databases. Test client via `httpx.AsyncClient` with FastAPI TestClient-style transport.

**What's tested** (15 test files in `tests/`):

| Test file | Scope |
|---|---|
| `test_unit_converter.py` | UnitConverter: normalization for all unit types, unknown units, edge cases |
| `test_ingredient_line_parser.py` | IngredientLineParser: quantity/unit/name extraction, German unit synonyms, unparseable lines, ranges, comma-separated prep notes |
| `test_normalizer.py` | IngredientNormalizer: alias resolution, fuzzy matching, threshold behavior, integration into the import pipeline |
| `test_matching_engine.py` | MatchingEngine: exact/partial/ingredient_first modes, scoring, urgency boost, reservations |
| `test_scraper.py` | RecipeScraper: caching, rate limiting, URL parsing |
| `test_auth.py` | Register, login, logout, session validation, password change |
| `test_household.py` | Household CRUD, invite codes, member management, meal templates, export |
| `test_ingredients.py` | Ingredient CRUD, aliases |
| `test_recipes.py` | Recipe CRUD, import, tags, favorites, notes, FTS search, soft delete |
| `test_inventory.py` | Inventory CRUD, category filtering |
| `test_weeks.py` | Week plan CRUD, slot updates, cooking, leftovers, visibility, ISO week logic |
| `test_grocery_list.py` | List generation, regeneration, item management, completion, sharing |
| `test_public_plan.py` | Public plan access, visibility rules |
| `test_health.py` | Health check endpoint |
| `test_user.py` | User favorites and notes listing |

**Frontend tests**: Vitest + jsdom + `@testing-library/react` + `@testing-library/jest-dom` + `@testing-library/user-event`. Vitest config lives at the frontend root; global setup at `frontend/src/test/setup.ts` (imports jest-dom matchers and stubs `matchMedia`). Path alias `@/` works in tests as it does in source.

| Test file | Scope |
|---|---|
| `src/hooks/useDarkMode.test.ts` | `useDarkMode`: `localStorage` round-trip, `matchMedia` fallback, `.dark` class application, `toggle()` writes back to storage. |
| `src/components/AppLayout.test.tsx` | `AppLayout`: topbar shows the title from `PageHeaderContext`; subtitle + actions render; authenticated username surfaces in the sidebar footer. |
| `src/components/ProtectedRoute.test.tsx` | `ProtectedRoute`: renders children when authenticated, redirects to `/login` when not, loading state is inline (no full-screen stretch). |
| `src/App.test.tsx` | `App` routing: `/` redirects to `/plan`; public routes (`/login`, `/register`, shared grocery list, shared week plan) render without the shell; unauthenticated users are bounced from protected routes; `/__shell-preview` is gone. |
| `src/pages/RecipeFormPage.test.tsx` | `RecipeFormPage` (split into five describe blocks: base form, ingredient rows, tag picker, URL import, plus a `RecipeListPage` URL import block): basic field rendering + submit + error render + `source_domain` blur derivation; `RecipeListPage` "Neues Rezept" action; ingredient row add/remove, combobox debounce + lock-on-click, submit body shape (order_index + parsed quantity, empty rows dropped); tag pills fetched on mount + toggle in/out, submit with tags fires POST then PUT `{ tag_ids }`, submit with no tags skips the PUT, PUT failure renders inline and keeps the created recipe; URL import — no fetch without `?url=`, success prefills the form and shows the "Importiert von" banner, "Verwerfen" clears the form and the query param, 422 leaves the form blank with the detail inline; `RecipeListPage` URL input + "Importieren" submits navigate to `/recipes/new?url=…`. |

**What's NOT tested**: `PageHeader` (trivial context-setter), `SidebarNav` (visual + NavLink integration), drag-and-drop, E2E workflows, visual behavior, the no-flash inline `<script>` in `index.html`. Hook- and route-level tests are in; granular component tests for `PageHeader`/`SidebarNav` are out until the frontend test story expands.

**Run tests**:
```bash
cd backend && uv run pytest
cd frontend && npm test            # vitest run
cd frontend && npm run test:watch   # vitest watch mode
```

**Lint and typecheck**:
```bash
cd backend && uv run ruff check . && uv run mypy .
cd frontend && npm run lint && npm run typecheck
```

## Out of Scope

Explicitly deferred from the PRD — if mentioned in a new issue, check `.out-of-scope/` for prior discussion:

- Individual dietary profiles per user (only per-slot tag filters exist)
- Notifications / reminders
- "Random recipe" button
- Nutritional values (calories, macros)
- Offline support / PWA
- Recipe timing (prep time vs. cook time)
- Calendar / iCal export of the week plan
- Embeddable widget for public plans
- Custom meal types (only the 4 fixed types: breakfast, lunch, dinner, dessert)
- Grocery list sharing with external services
- Multiple recipes per meal slot (simplified to 1 recipe per slot)
- Receipt scanning for inventory
