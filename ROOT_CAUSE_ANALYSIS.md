# ROOT CAUSE ANALYSIS

---

## Issue: Dark mode completely broken on app pages

**Root Cause:** Two-phase implementation inconsistency. The theme system was correctly implemented:
1. CSS variables in `globals.css` with `.dark` class selectors
2. `next-themes` with `attribute="class"` adding/removing `dark` class
3. `darkMode: ["class", ".dark"]` in Tailwind config

These work correctly for the **landing page** because all landing components were audited and migrated to use CSS variable tokens (`bg-background`, `text-foreground`, `border-border`).

However, the **app pages** (analysis, history, settings) were never migrated. Every component in the app uses hardcoded Tailwind neutral values (`bg-white`, `border-neutral-200`, `text-neutral-900`, etc.) which resolve to the same color regardless of the `.dark` class on `<html>`.

**Impact:** Users see white backgrounds, black text, and broken contrast in dark mode on all non-landing pages.
**Fix Strategy:** Migrate every app-page component to CSS variable tokens. Replace `bg-white` → `bg-background`, `border-neutral-200` → `border-border`, `text-neutral-900` → `text-foreground`, etc.

---

## Issue: Theme toggle missing from app NavBar

**Root Cause:** The `ThemeToggle` was added only to the landing-page variant of the NavBar (the `isLanding` branch). The app-nav variant (used on `/analysis`, `/history`, `/settings`) does not include `ThemeToggle`.

**Impact:** Users cannot toggle theme from app pages.
**Fix Strategy:** Add `<ThemeToggle />` to the non-landing NavBar variant.

---

## Issue: MetricsSection inverted in light mode

**Root Cause:** `MetricsSection.tsx` was changed from `bg-black text-white` to `bg-foreground text-background`. This is semantically correct for dark mode (near-white bg, near-black text) but becomes visually wrong in light mode (near-black bg, white text = inverted section).

The section was INTENDED to be a visually dark section regardless of theme. But `bg-foreground` is light in dark mode and dark in light mode — it's a theme-aware semantic token, not a static color.

**Impact:** In light mode, the metrics section is nearly black with white text, while the rest of the page is white — visually jarring.
**Fix Strategy:** Use a dedicated CSS variable for the dark section background, e.g., add `--color-section-dark` or use `bg-foreground text-background` BUT only for dark mode, or use an inline approach for this specific section.

---

## Issue: `test_bug_hunter_finds_issues` fails

**Root Cause:** `BugHunterAgent` calls analysis tools (`detect_syntax_errors`, `find_unused_imports`, etc.) which are **stub implementations** returning `{"patterns": []}`. The agent budget runs out without finding any issues, so the test assertion fails.

**Impact:** End-to-end demo produces 0 detected issues even for the `buggy_calculator` example which contains real bugs.
**Fix Strategy:** Implement actual detection logic in `agira/tools/analysis_tools.py` stub functions.

---

## Issue: ESLint error — setState in useEffect

**Root Cause:** `analysis/page.tsx` calls `startAnalysis()` (which calls `setJobId` and `setStatus`) synchronously inside a `useEffect`. ESLint's `react-hooks/set-state-in-effect` rule flags this because calling setState synchronously within an effect can cause cascading renders.

**Impact:** ESLint error in CI.
**Fix Strategy:** Use an event-driven initialization pattern — call `startAnalysis` in a `useCallback`-wrapped handler triggered by the effect, rather than directly.

---

## Issue: `adaptive_planning` missing from Settings UI

**Root Cause:** `TOGGLES` array in `SettingsPanel.tsx` has 4 hardcoded entries, omitting `adaptive_planning`.

**Impact:** Users can't toggle the adaptive planning setting even though the backend supports it.
**Fix Strategy:** Add `adaptive_planning` to the `TOGGLES` array.

---

## Issue: Pytest failure — 10 pass, 1 fail

**Root Cause:** Same as "test_bug_hunter_finds_issues" — analysis tool stubs return empty data.

**Impact:** CI cannot be considered passing.
**Fix Strategy:** Implement stub analysis tools or mock them for the test.

---

## Issue: No loading/error boundaries

**Root Cause:** Next.js App Router error/loading conventions not implemented. No `error.tsx` or `loading.tsx` files.

**Impact:** Any unhandled exception shows a blank white screen.
**Fix Strategy:** Add `error.tsx` files to each route. Add `loading.tsx` for loading states.

---

## Issue: GitHub clone non-functional

**Root Cause:** `resolveRepoPath` in `frontend/src/lib/server/jobs.ts` and the corresponding logic in `agira/orchestrator/planner.py` accept `repo_url` but return a hardcoded demo path.

**Impact:** Users cannot analyze real GitHub repositories.
**Fix Strategy:** Implement `git clone` for `repo_url` inputs.

---

## Issue: No API authentication

**Root Cause:** All 5 API routes (`/api/analyze`, `/api/history`, `/api/memory`, `/api/report`, `/api/settings`) have no authentication middleware.

**Impact:** Full system access for any client.
**Fix Strategy:** Add `X-API-Key` header validation via environment variable.

---

## Issue: Path traversal risk

**Root Cause:** `resolveRepoPath()` in `agira/orchestrator/planner.py` accepts absolute `repo_path` values without validating they are within an allowed directory.

**Impact:** Users can analyze arbitrary paths on the filesystem.
**Fix Strategy:** Validate that resolved paths are within `PROJECT_ROOT` or the temp work directory.