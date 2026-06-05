# CI pipeline

The CI pipeline is defined in `.github/workflows/ci.yml` and runs on every push to `main` and on every pull request targeting `main`. It is the project's quality gate: a PR with a failing CI is not considered mergeable.

The pipeline consists of three independent jobs. If the frontend job fails, the backend job still runs, and vice versa. The audit job always runs regardless of the other jobs' outcomes.

## Jobs

### backend

Runs in the `backend/` directory using Python 3.12 and `uv`.

| Step | What it does |
|------|-------------|
| `uv sync --frozen` | Installs backend dependencies exactly as pinned in `uv.lock`. The `--frozen` flag prevents accidental updates to the lock file. |
| `uv run ruff check .` | Lints the codebase with ruff. Ruff checks for style violations (E), logical errors (F), import ordering (I), and warnings (W) as configured in `[tool.ruff.lint]`. |
| `uv run mypy app` | Runs mypy in strict mode on the `app/` directory. All type errors must be resolved — no `# type: ignore` without a strong reason. |
| `uv run pytest -v` | Runs the full test suite with verbose output. Tests use `pytest-asyncio` with `asyncio_mode = "auto"` and are distributed across CPU cores with `pytest-xdist`. |

The lint and type-check steps are fast and run before the tests. Fixing them first saves time, since a type error will block you from even running the test suite successfully.

### frontend

Runs in the `frontend/` directory using Node.js 24.

| Step | What it does |
|------|-------------|
| `npm ci` | Installs frontend dependencies exactly as pinned in `package-lock.json`. Like `--frozen` on the backend, this guarantees reproducible installs. |
| `npm run lint` | Runs ESLint across the entire frontend codebase. |
| `npm run typecheck` | Runs `tsc -b` — TypeScript's project-level build mode — to verify that the entire project type-checks without errors. |

### audit

Runs dependency vulnerability scans for both the backend and the frontend. This job runs on every CI invocation, not just on a schedule, so a newly published CVE will be caught on the next push.

| Step | What it does |
|------|-------------|
| `uv run pip-audit` | Scans the backend's Python dependencies for known vulnerabilities (CVEs) using the pip-audit tool. Results are saved as `audit-backend.json` and uploaded as a CI artifact. |
| `npm audit --audit-level=high` | Scans the frontend's Node.js dependencies with `npm audit`. Only high-severity and critical findings cause the step to fail. Results are saved as `audit-frontend.txt` and uploaded as a CI artifact. |

## Running checks locally

CI failures discovered only after pushing waste time. Run the same checks locally before you commit.

### Backend

All commands are run from the `backend/` directory.

```bash
cd backend

# Install dependencies (do this first if you've pulled new changes)
uv sync

# Lint
uv run ruff check .

# Auto-fix lint issues where possible
uv run ruff check . --fix

# Type check
uv run mypy app

# Run tests
uv run pytest -v
```

Run them in that order: lint first (fast, catches obvious problems), then type-check (fast, catches structural errors), then tests (slower, catches logic errors).

### Frontend

All commands are run from the `frontend/` directory.

```bash
cd frontend

# Install dependencies
npm install

# Lint
npm run lint

# Type check
npm run typecheck

# Run frontend tests (Vitest)
npm run test
```

Note: the CI only runs lint and type-check for the frontend. Frontend tests (`npm run test`) are not yet part of the CI pipeline but should be run locally before pushing changes to test code.

### Vulnerability audit

```bash
# Backend
cd backend
uv run pip-audit

# Frontend
cd frontend
npm audit --audit-level=high
```

## What to do when a check fails

### Ruff (lint)

Ruff failures are the most common and most mechanical to fix. Read the error output carefully — ruff tells you the file, line number, and rule code for every violation.

- **E errors** (pycodestyle): whitespace, line length, blank line placement. Run `uv run ruff check . --fix` — ruff can auto-fix most of these.
- **F errors** (Pyflakes): undefined names, unused imports, unused variables. These usually point to real bugs or dead code. Remove unused imports; investigate undefined names.
- **I errors** (isort): import ordering. Run `--fix` to auto-sort imports.
- **W errors** (pycodestyle warnings): stylistic warnings. Address them or, in rare justified cases, add a `# noqa: Wxxx` comment.

After addressing issues, run `uv run ruff check .` again to confirm a clean run.

### mypy (type checking)

Mypy errors fall into two broad categories:

1. **Your code has a real type bug.** You're passing a `str | None` where a `str` is expected, or you're calling a method that doesn't exist on the type you have. Fix the logic so the types align.

2. **Mypy is over-strict and you know the code is correct.** Before reaching for `# type: ignore`, ask yourself whether a small restructure could make the types clear to mypy as well. If not, add `# type: ignore[<error-code>]` with the specific error code — never a bare `# type: ignore`. Include a comment explaining why it's safe.

Common mypy errors in this project:

| Error | Likely cause |
|-------|-------------|
| `X has no attribute "Y"` | You're accessing a column or relationship that hasn't been loaded. Use `selectinload()` or adjust the query. |
| `Incompatible types in assignment` | Mismatch between the declared type and the assigned value. Check the function signature and the value origin. |
| `Item "None" of "Optional[X]" has no attribute "Y"` | You're not guarding against `None`. Add an `if value is not None:` check or use a type-narrowing pattern. |

### pytest (tests)

- **Assertion failure**: Read the assertion to understand what went wrong. If the test expectation is outdated (the behaviour changed intentionally), update the test. If the behaviour change was unintentional, fix the code.
- **Import error / missing fixture**: Usually means a dependency was removed or renamed. Check `pyproject.toml` and your imports.
- **Test timeout or hang**: Likely an async resource leak — a fixture doesn't clean up after itself, or a mock isn't being properly closed.

### ESLint (frontend lint)

ESLint errors include rule IDs that you can look up. Common causes:

- Unused variables (remove them)
- Missing hook dependencies in `useEffect` / `useMemo` (add the missing dependency or restructure the code)
- Accessibility violations (add `aria-label`, roles, or alt text)
- Import statements that can't be resolved (check the file path)

### TypeScript type checking (frontend)

`npm run typecheck` runs `tsc -b`, which type-checks the entire project against `tsconfig.json`. Look for:

- Type mismatches in props, state, or function signatures
- Missing properties on an object type
- Incorrect generic parameters
- Imports from paths that don't exist or have moved

### Dependency audit failures

A `pip-audit` or `npm audit` failure means a dependency has a known vulnerability with severity `high` or `critical`.

1. Check if a newer patch version of the dependency exists that fixes the vulnerability.
2. Update the dependency in `pyproject.toml` (backend) or `package.json` (frontend) to the patched version.
3. Regenerate the lock file: `uv lock` for backend, `npm install` for frontend.
4. Run the audit again to confirm the fix.

If no patch exists yet, open an issue with the `needs-triage` label describing the affected dependency and the CVE. The team can assess whether the vulnerability is exploitable in this application's context.

## Pre-commit verification workflow

Before pushing a branch or opening a pull request, run these checks in order:

```
1. cd backend && uv run ruff check . && uv run mypy app && uv run pytest -v
2. cd frontend && npm run lint && npm run typecheck && npm run test
```

If all three backend steps and all three frontend steps pass, your branch is in the same state CI expects. Push with confidence.

If you're only changing one side of the stack (backend-only or frontend-only), you can skip the other side's checks — CI will still run them, but the risk of a surprise failure is low.

### After merging PRs from other contributors

When you pull `main` after someone else's PR was merged, always run:

```bash
cd backend && uv sync
cd frontend && npm install
```

Dependencies may have changed. Running the full local verification afterwards catches integration issues before your next push.
