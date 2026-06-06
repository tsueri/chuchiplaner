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
| **Recipe** | A meal imported from a Swiss cooking site or created manually. Contains title, description (optional short summary), an ordered list of RecipeSteps, image_url, source_url, source_domain, servings (default 4), the four ISO 8601 durations stored as integer minutes (prep_time_minutes, cook_time_minutes, total_time_minutes, perform_time_minutes, all nullable), a free-form `nutrition` blob holding a schema.org/NutritionInformation object (nullable), a free-form `aggregate_rating` blob holding a schema.org/AggregateRating object when the source publishes one (nullable, no edit UI — out of our users' hands), a free-text comma-separated `keywords` column, `author` (nullable string), `date_published` (nullable date), and a list of RecipeIngredients. Soft-deleted via `deleted_at`. `(household_id, source_url)` is unique among non-deleted rows. `POST /api/recipes` with a `source_url` collision returns 409 with the existing recipe's id **only** when the request body does not set `reimport=true`; that gate is the manual-create path. When the body sets `reimport=true` (the import flow sends this when the upstream `POST /api/recipes/import` already saw `existing_recipe_id` set), a `source_url` collision is an **upsert** — the existing row is overwritten with the new body (title, description, times, steps, ingredients, tags, image_url, servings, source_domain) and the response is the updated `RecipeDetailResponse` for that row. Editable by any household member; delete remains admin-only. |
| **RecipeStep** | One ordered step on a Recipe. Fields: `recipe_id`, `position` (0-indexed), `text`, `name` (optional short label, e.g. "Teig zubereiten"). Detail page renders as `<ol>`; each step's `text` is one numbered item, and the `name` (when present) renders as an `<h3>` sub-heading above the step text. Unique on `(recipe_id, position)`. Cascade-deletes with the parent Recipe on hard delete (soft delete preserves the rows). Migration from the old single `instructions: Text` field: each existing recipe's full text becomes a single step at `position=0`, no heuristic splitting. |
| **RecipeIngredient** | A line on a Recipe. Fields: `ingredient_id`, `quantity`, `unit`, `order_index`. The read response also carries `ingredient_name: str` (the joined canonical Ingredient name) on every row, so the UI can render the line as `{quantity} {unit} {ingredient_name}` without a second lookup. |
| **RecipeTag** | A tag attached to a Recipe. Tags have a `group`: `"season"` (fixed: Frühling/Sommer/Herbst/Winter/Ganzjährig, global `household_id IS NULL`, multi-value per recipe), `"ingredient"` (free-form per household, `household_id` is the owning household), `"category"` (global controlled vocabulary: Vorspeise/Hauptgericht/Dessert/Snack/Beilage, exactly one per recipe), `"cuisine"` (global controlled vocabulary: Italienisch/Asiatisch/Schweizerisch/Mexikanisch/Indisch/Französisch, exactly one per recipe), or `"diet"` (global, multi-value per recipe, vocabulary mirrors schema.org `RestrictedDiet`: `VegetarianDiet`, `VeganDiet`, `GlutenFreeDiet`, `LowFatDiet`, `LowLactoseDiet`, `DiabeticDiet`, `HalalDiet`, `KosherDiet`). The one-per-recipe rule for `category` and `cuisine` is enforced server-side by the `PUT /api/recipes/:id` `tag_ids` handler: when any incoming tag belongs to one of those two groups, every existing recipe tag of that group is removed before the new set is applied, so saving a new `category` automatically replaces the previous one. `season` and `diet` remain multi-value. `GET /api/tags` returns all five groups; the standard global tags (season, category, cuisine, diet) are seeded by alembic migration `c2d3e4f5g6h7` and have `household_id IS NULL`. `POST /api/tags` accepts a `group` field validated against `{season, ingredient, category, cuisine, diet}`; global groups are stored with `household_id = NULL`, `ingredient` tags are stored with the calling household's id. The MealSlot's `dietary_filter_tag_id` resolves to a `diet` group tag; the week-plan filter therefore matches the schema.org vocabulary, and any future dietary-filter picker must read only tags with `group === "diet"`. |
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
| **DurationSerializer** | Static utility for the four ISO 8601 duration fields on Recipe. `to_iso_duration(minutes)` → `"PT1H30M"` (None in → None out); `from_iso_duration(iso)` → minutes, truncating `PT45S` to `0` and returning `None` for garbage; `format_human(minutes)` → German string (`"1 Std. 30 min"`, `"45 min"`, `"1 Std."`); `parse_human(human)` → minutes, accepting `"1h 30m"`, `"90 min"`, `"1:30"`, `"2 Std."`, `"2.5h"`, returning `None` for anything else. Pure module — same shape as `UnitConverter`. |
| **RecipeJSONLDExporter** | Static utility: `to_jsonld(recipe: Recipe) -> dict` emits a schema.org/Recipe JSON-LD node with `@context: "https://schema.org"` and `@type: "Recipe"`. Every non-null field on the recipe becomes the corresponding schema.org property. Time fields use `DurationSerializer.to_iso_duration` for ISO 8601 output. Tags are split by group: `category` → `recipeCategory` (string), `cuisine` → `recipeCuisine` (string), `diet` → `suitableForDiet` (list of `https://schema.org/<dietName>` URIs). Steps become `recipeInstructions`: one `HowToStep` per step, with optional `name`. Ingredients become `recipeIngredient`: joined canonical names. `nutrition`, `aggregateRating` pass through verbatim (already stored in schema.org shape). `keywords` is the raw comma-separated string. `identifier` is the recipe's integer `id`. Season and ingredient-group tags are ignored. Missing fields are absent, not `null`. Used by the household export endpoint to produce the `recipes_as_jsonld` block.|
| **FTSRebuilder** | Single source of truth for the `recipes_fts` virtual table (columns: `title, description, steps, ingredients, keywords, author, tags`) and its per-column bm25 weights (`ingredients=5.0`, `steps=3.0`, `description=3.0`, others=1.0). `rebuild(db)` drops and recreates the table and repopulates by joining `recipes` to `recipe_steps`, `recipe_ingredients`, and `tags` (soft-deleted rows skipped). `reindex_one(db, recipe_id)` rewrites a single row using the same join — independent of in-memory ORM state — and is called by `create_recipe` / `update_recipe`. `delete_one(db, recipe_id)` removes a row and is called by the soft-delete path. `weights_sql()` returns the bm25 weights in column order for `ORDER BY bm25(recipes_fts, …)` in the search endpoint. |
| **IngredientLineParser** | Splits a raw scraped ingredient string (e.g. `"600g Kalbfleisch"`, `"1 Zwiebel, gehackt"`) into `(quantity, unit, name)`. Returns `quantity=None, unit=None, name=line` for unparseable lines (e.g. `"Salz und Pfeffer"`). Uses the source-side unit vocabulary — canonical synonyms (Esslöffel, Teelöffel, Dose, Becher, …) plus the standard `UnitConverter` set — and is the only module that knows those synonyms. Unit name maps to the canonical form (`"EL"` not `"Esslöffel"`). Ranges (`"2-3 EL"`) collapse to the lower bound. |
| **IngredientNormalizer** | Resolves parsed ingredient names to canonical Ingredient IDs. Uses household aliases first, then exact name match, then fuzzy matching (SequenceMatcher, threshold 0.6). Returns `(ingredient_id, confidence)` where 1.0 means exact/alias. |
| **IngredientNameCleaner** | Tier 1 of the ingredient cleanup pipeline. Wraps a fine-tuned German NER model (distilbert-base-german-cased, token classification with B-ING/I-ING/O labels) that strips adjectives, preparation notes, parentheticals, and regional modifiers from ingredient names. Loaded at app startup into process memory. Fails fast on load error — import endpoint is unavailable until the model is fixed. Returns original name on inference error (graceful degradation per-request). |
| **IngredientLLMResolver** | Tier 2 of the ingredient cleanup pipeline. Batch-processes hard ingredient lines through an Ollama sidecar (default model: `qwen3.5:2b`, configurable via `OLLAMA_MODEL` env var). Handles edge cases: alternatives ("X oder Y"), equipment detection, embedded weight specs ("à 300 g"), word-form quantities. 10s timeout; on failure returns empty results and falls through to `IngredientNormalizer`. |
| **IngredientCleanupPipeline** | Orchestrates the two-tier cleanup: `IngredientLineParser` → `IngredientNameCleaner` (Tier 1) → `IngredientNormalizer` → `IngredientLLMResolver` (Tier 2, for hard lines only). Returns `ScrapedIngredientItem` with `tier1_cleaned_name`, `tier2_cleaned_name`, `corrected_quantity`, `corrected_unit`, `suggested_ingredient_name`, `is_equipment` populated where available. Degrades gracefully when Tier 2 is unavailable. |
| **ScrapedIngredientItem** | Per-scraped-line payload inside the import response. Fields: `raw` (original string), `name` (parsed), `quantity` (float or null), `unit` (canonical form or null), `ingredient_id` (matched canonical or null), `confidence` (0.0–1.0), `tier1_cleaned_name` (NER-cleaned name), `tier2_cleaned_name` (LLM-cleaned name), `corrected_quantity` (LLM-corrected quantity), `corrected_unit` (LLM-corrected unit), `suggested_ingredient_name` (for new ingredient creation), `is_equipment` (whether the line is non-food equipment). The form pre-fills one row per item, locking rows at confidence 1.0, pre-selecting the suggestion at 0.6–1.0, leaving rows open at < 0.6, and showing a "Neu" badge when `suggested_ingredient_name` is present. |
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

**Search**: FTS5 virtual table (`recipes_fts`) on the seven columns `(title, description, steps, ingredients, keywords, author, tags)`. Populated on create/update via raw SQL through `FTSRebuilder` (`app/services/fts_rebuilder.py`). The search endpoint orders FTS hits by `bm25` with per-column weights — `ingredients` (5.0) ranks above `steps`/`description` (3.0) which rank above `title` (1.0); `keywords`/`author`/`tags` carry the default 1.0 weight — so a query that matches an ingredient name returns the recipe even when the word never appears in the title or steps. The LIKE fallback on `title` still applies when FTS returns nothing.

**Backup**: Docker sidecar (`backup/`) copies the SQLite file daily with 7-day retention. Manual JSON export button in settings (`GET /api/household/export`). The export now also emits a `recipes_as_jsonld` block with `@context: "https://schema.org"` and a `@graph` of all recipes serialised as schema.org/Recipe nodes via `RecipeJSONLDExporter`, so the backup file can be consumed by any schema.org-aware tool (e.g. Google Rich Results validator).

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
│       ├── duration_serializer.py  # Static utility: ISO 8601 ↔ minutes ↔ German human strings
│       ├── recipe_jsonld_exporter.py  # Static utility: Recipe → schema.org/Recipe JSON-LD node
│       ├── fts_rebuilder.py   # FTSRebuilder: rebuild(db) / reindex_one(db, id) / delete_one(db, id) / weights_sql()
│       ├── normalizer.py          # IngredientNormalizer: resolve(name, aliases) → (id, confidence), learn_alias()
│       ├── ingredient_name_cleaner.py    # IngredientNameCleaner: NER-based ingredient name cleaning (Tier 1)
│       ├── ingredient_cleanup_pipeline.py # IngredientCleanupPipeline: orchestrates Tier 1→Tier 2→normalizer
│       └── ingredient_llm_resolver.py    # IngredientLLMResolver: Ollama batch resolver for hard lines (Tier 2)
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
│   ├── RecipeFormPage.tsx     # Create-recipe form: basic fields + tag pills (fetched from /api/tags on mount, toggled locally) + dynamic ingredient rows (combobox with debounced /api/ingredients?q=…, quantity, unit, remove). Clicking a result locks the row; empty rows dropped on submit. Submit is POST /api/recipes, then PUT /api/recipes/<id> { tag_ids } only if any tags are selected; PUT failure renders inline, recipe kept. URL import: when mounted with a `?url=` query param, calls POST /api/recipes/import on mount, prefills the six basic fields, and shows an "Importiert von <domain>" banner with a "Verwerfen" action that resets the form and strips the `url` query param. A non-2xx import response renders the detail message inline and leaves the form blank. When the import response carries `existing_recipe_id`, submit PUTs the full scraped state to `/api/recipes/:existing_recipe_id` and navigates to that detail page — the manual-create POST path and the 409-soft-warning UI are skipped in that branch.
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
Full-text search uses a virtual `recipes_fts` table with seven columns: `(title, description, steps, ingredients, keywords, author, tags)`. Populated on recipe create/update via raw SQL in `FTSRebuilder.reindex_one`; rebuilt in bulk via `FTSRebuilder.rebuild` (used by the slice 1 migration and available as a runtime tool). The search endpoint orders FTS hits by `bm25(recipes_fts, …)` with per-column weights from `FTSRebuilder.WEIGHTS` — `ingredients=5.0`, `steps=3.0`, `description=3.0`, `title=1.0`, `keywords=1.0`, `author=1.0`, `tags=1.0` — so a hit in `ingredients` ranks above a hit in `steps`/`description`, which rank above a hit in `title`. When FTS returns no rows the endpoint falls back to a `Recipe.title.contains(search)` SQL LIKE so partial-prefix queries (e.g. `"Spagh"`) still resolve.

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

**What's tested** (20 test files in `tests/`):

| Test file | Scope |
|---|---|
| `test_unit_converter.py` | UnitConverter: normalization for all unit types, unknown units, edge cases |
| `test_ingredient_line_parser.py` | IngredientLineParser: quantity/unit/name extraction, German unit synonyms, unparseable lines, ranges, comma-separated prep notes |
| `test_normalizer.py` | IngredientNormalizer: alias resolution, fuzzy matching, threshold behavior, integration into the import pipeline |
| `test_ingredient_name_cleaner.py` | IngredientNameCleaner: NER model inference, adjective stripping, prep note removal, edge cases |
| `test_ingredient_llm_resolver.py` | IngredientLLMResolver: regex routing, LLM response parsing, batch construction, timeout, error handling |
| `test_ingredient_cleanup_pipeline.py` | IngredientCleanupPipeline: Tier 1→Tier 2 routing logic, fallback behavior, integration |
| `test_matching_engine.py` | MatchingEngine: exact/partial/ingredient_first modes, scoring, urgency boost, reservations |
| `test_scraper.py` | RecipeScraper: caching, rate limiting, URL parsing |
| `test_auth.py` | Register, login, logout, session validation, password change |
| `test_household.py` | Household CRUD, invite codes, member management, meal templates, export |
| `test_ingredients.py` | Ingredient CRUD, aliases |
| `test_recipes.py` | Recipe CRUD, import, tags, favorites, notes, FTS search (bm25-ranked + LIKE fallback), soft delete |
| `test_recipe_jsonld_exporter.py` | `RecipeJSONLDExporter.to_jsonld`: minimal recipe, all fields, durations, tags by group, diet URIs, HowToSteps, pass-through fields |
| `test_fts_rebuilder.py` | FTSRebuilder: column / weight invariants, full rebuild from join, ingredient-only search, soft-delete skip, per-row reindex / delete |
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
- Offline support / PWA
- Calendar / iCal export of the week plan
- Embeddable widget for public plans
- Custom meal types (only the 4 fixed types: breakfast, lunch, dinner, dessert)
- Grocery list sharing with external services
- Multiple recipes per meal slot (simplified to 1 recipe per slot)
- Receipt scanning for inventory
