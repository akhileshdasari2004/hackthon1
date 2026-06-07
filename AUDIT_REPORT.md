# AGIRA FULL SYSTEM AUDIT REPORT

## 1. CRITICAL ISSUES

### C-1: Dark Mode Completely Broken on App Pages
**Severity: CRITICAL**
Theme system (next-themes, CSS variables, .dark class) works correctly on the landing page only. ALL app pages and components use hardcoded Tailwind neutral color values and are completely immune to dark mode toggling.

**Affected files:**
- `frontend/src/app/analysis/page.tsx` — `bg-white`, `border-neutral-200`, `text-neutral-500`, `text-neutral-900`
- `frontend/src/components/RepositoryUploader.tsx` — `bg-neutral-900 text-white`, `border-neutral-200`, `bg-neutral-50`
- `frontend/src/components/NodeCard.tsx` — `border-neutral-200`, `text-neutral-900`, `bg-neutral-50`
- `frontend/src/components/HistoryCard.tsx` — `bg-white`, `border-neutral-200`, `text-neutral-900`
- `frontend/src/components/HealthScoreCard.tsx` — `border-neutral-200`, `text-neutral-900`
- `frontend/src/components/SettingsPanel.tsx` — `border-neutral-200`, `text-neutral-900`
- `frontend/src/components/ReportTabs.tsx` — `border-neutral-200`, `text-neutral-900`
- `frontend/src/components/ui/tabs.tsx` — `bg-neutral-100`, `bg-white`, `text-neutral-500`, `text-neutral-900`
- `frontend/src/components/ui/switch.tsx` — `border-neutral-200`, `bg-neutral-100`, `bg-neutral-900`
- `frontend/src/components/ui/input.tsx` — `border-neutral-200`, `bg-white`, `text-neutral-900`
- `frontend/src/components/landing/MetricsSection.tsx` — `bg-black text-white` (inverted — correct only for dark mode, breaks light mode)
- `frontend/src/components/landing/DemoPreview.tsx` — `bg-white` (broken in dark mode)
- `frontend/src/components/landing/ProductShowcase.tsx` — `bg-white` (broken in dark mode)
- `frontend/src/components/landing/StorySection.tsx` — `bg-white` (broken in dark mode)
- `frontend/src/components/landing/FinalCTA.tsx` — `bg-white` (broken in dark mode)
- `frontend/src/components/landing/EngineSection.tsx` — `bg-muted` ✅ (CSS variable, correct)

**Root Cause:** Landing page components were migrated to CSS variable tokens (`bg-background`, `text-foreground`, `border-border`). App page components were never migrated.
**Impact:** App users in dark mode see white backgrounds, unreadable text, broken contrast.
**Fix:** Replace all hardcoded neutral Tailwind values in app components with CSS variable tokens matching the pattern used on the landing page.

---

### C-2: No Authentication on Any API Route
**Severity: CRITICAL — SECURITY**
All 5 API routes accept requests without any authentication or authorization:
- `POST /api/analyze` — anyone can trigger analysis
- `GET /api/history` — anyone can read full job history
- `GET /api/memory` — anyone can read memory store (may contain secrets/patterns)
- `GET /api/report` — anyone can read any job's report
- `PUT /api/settings` — anyone can modify system settings

**Root Cause:** API routes are unauthenticated by design.
**Impact:** Any client can trigger analysis, read data, modify settings.
**Fix:** Add API key / session token validation to all routes. At minimum, add `X-API-Key` header check via env var.

---

### C-3: GitHub Clone Is a Stub
**Severity: CRITICAL — FUNCTIONALITY**
`resolveRepoPath()` in `frontend/src/lib/server/jobs.ts` and `agira/orchestrator/planner.py` accepts `repo_url` but always returns `examples/buggy_calculator` — no actual GitHub cloning is implemented.

**Root Cause:** `repo_url` branch in `resolveRepoPath()` is a stub that returns hardcoded demo path.
**Impact:** Users cannot analyze actual GitHub repositories — only local paths or the demo fixture.
**Fix:** Implement `git clone` via `subprocess.run(["git", "clone", "--depth", "1", repo_url, work_dir])`.

---

### C-4: Path Traversal / Arbitrary File Read
**Severity: CRITICAL — SECURITY**
`resolveRepoPath()` accepts absolute paths without sandboxing. If a user provides `repo_path="/etc/passwd"`, the system will attempt to analyze it.

In `agira/tools/repo_tools.py` (not fully read), file operations may read arbitrary paths outside the intended repository scope.

**Root Cause:** No path validation or sandboxing.
**Impact:** Users can read arbitrary files on the filesystem via the analysis pipeline.
**Fix:** Validate all paths are within an allowed root directory (e.g., project root or temp work dir).

---

### C-5: Missing Error and Loading Boundaries
**Severity: HIGH**
No `error.tsx` or `loading.tsx` files exist anywhere in the Next.js app. Any unhandled error or slow network request produces a blank/error-prone page.

**Root Cause:** Not implemented.
**Impact:** Runtime errors show blank white screens.
**Fix:** Add `error.tsx` to each route and `loading.tsx` for Suspense boundaries.

---

## 2. HIGH PRIORITY ISSUES

### H-1: MetricsSection Color Inversion
`MetricsSection.tsx` uses `bg-foreground text-background`. In dark mode, `bg-foreground` = `#fafafa` (near-white) and `text-background` = `#09090b` (near-black). This looks correct in dark mode. In light mode, `bg-foreground` = `#09090b` (black) and `text-background` = `#ffffff` (white) — creating a black section with white text. This is INVERTED from the intended design (section should be dark in both modes).

**Root Cause:** `bg-black text-white` was replaced with `bg-foreground text-background` without accounting for the semantic meaning (the section is MEANT to be visually dark).
**Fix:** Either use a dedicated dark section color token, or use inline style for this specific section.

---

### H-2: Pytest Failure — `test_bug_hunter_finds_issues`
**Severity: HIGH — TEST**
`tests/test_subagents.py:37` — BugHunterAgent returns 0 issues because all `analysis_tools` detection functions are stubs returning empty data.

**Root Cause:** `analysis_tools` implementations (`detect_syntax_errors`, `find_unused_imports`, `detect_hardcoded_secrets`, etc.) are stubs that return `{"patterns": []}`.
**Impact:** BugHunterAgent never finds real bugs, breaking the end-to-end demo.
**Fix:** Implement real detection logic in `agira/tools/analysis_tools.py`.

---

### H-3: ESLint Error — setState in useEffect
**Severity: MEDIUM — CODE QUALITY**
`frontend/src/app/analysis/page.tsx:79` — `startAnalysis({ repo_path: "examples/buggy_calculator" })` called inside `useEffect`. Triggers `react-hooks/set-state-in-effect` ESLint error.

**Root Cause:** `startAnalysis` calls `setJobId` and `setStatus` synchronously in an effect body.
**Fix:** Move state-setter calls out of the effect body, or use an event-driven pattern.

---

### H-4: Unused Import
**Severity: LOW — CODE QUALITY**
`frontend/src/components/ReportTabs.tsx:4` — `Patch` type imported but never used.

**Root Cause:** Dead import.
**Fix:** Remove `Patch` from the import line.

---

### H-5: Polling Without Backoff
**Severity: MEDIUM — PERFORMANCE**
`useAnalysisPolling` polls every 1500ms with no backoff or jitter. If multiple clients poll simultaneously, the backend could be overwhelmed.

**Root Cause:** Fixed interval polling.
**Fix:** Add exponential backoff with jitter after sustained polling.

---

### H-6: `adaptive_planning` Setting Not Connected
**Severity: MEDIUM**
`SettingsPanel.tsx` renders 4 toggles but `TOGGLES` array omits `adaptive_planning`. The settings are persisted but `adaptive_planning` is missing from the UI.

**Root Cause:** `TOGGLES` array hardcodes only 4 settings.
**Fix:** Add `adaptive_planning` to the `TOGGLES` array.

---

## 3. MEDIUM PRIORITY ISSUES

### M-1: `MemoryStore` Saves After Every Operation
`MemoryStore.record_failure()`, `record_success()`, etc. all call `self._save()` which writes to disk on every single call. During a run with many node failures, this causes excessive disk I/O.

**Root Cause:** No write batching — every record triggers a synchronous file write.
**Fix:** Debounce saves or use an in-memory buffer flushed on interval.

---

### M-2: `syncHistoryFromJobs()` O(n) File Reads
Every `GET /api/history` iterates ALL job directories and reads `result.json` for each one, then filters to non-duplicate entries. With many jobs this is slow.

**Root Cause:** No history caching. Full scan on every request.
**Fix:** Cache history in memory or use the existing `.agira-history.json` as source of truth without rescanning.

---

### M-3: `framer-motion` Heavy Bundle
`framer-motion` is imported in many landing page components. Most animations could use CSS `@keyframes` instead, reducing bundle size.

**Root Cause:** Overuse of framer-motion for simple opacity/transform animations.
**Fix:** Replace simple animations (opacity fade, y translate) with CSS animations. Keep framer-motion only for scroll-linked animations.

---

### M-4: Theme Toggle Missing in App NavBar
`NavBar.tsx` (non-landing mode) does NOT include `<ThemeToggle />`. Users on app pages cannot toggle themes.

**Root Cause:** ThemeToggle only added to the landing nav variant.
**Fix:** Add ThemeToggle to the non-landing nav variant as well.

---

### M-5: `MetricsSection` Uses Hardcoded Color Inversion (Related to C-1)
While `MetricsSection` uses `bg-foreground text-background`, this happens to work in dark mode but is semantically wrong and breaks in light mode.

---

## 4. TECHNICAL DEBT

- `RepositoryUploader` uses `useState` for mode (`"url"` | `"path"`) — this is fine but the mode toggle lacks `aria-pressed`
- `Switch` component has hardcoded `border-neutral-200 bg-neutral-100` — not dark-mode aware
- `Input` component has hardcoded `border-neutral-200 bg-white` — not dark-mode aware
- `Tabs` component has hardcoded `bg-neutral-100 bg-white` — not dark-mode aware
- `DAGGraph` uses hardcoded `border-neutral-200` in `statusColor()` return values in `dag.ts`
- `HistoryCard` wraps in `motion.div` from framer-motion but doesn't use any animation props (useless wrapper)
- `ExecutionTimeline`, `PatchViewer`, `MemoryPanel` were not fully inspected — unknown dark mode status

## 5. DEAD CODE

- `ReportTabs.tsx` line 4: `Patch` import unused
- `analysis/page.tsx` line 50: `isLoading` from `useAnalysisStore` is destructured but never used
- `analysis/page.tsx` line 53: `repoInfo` used once for display but could be inlined
- `ThemeToggle.tsx`: `THEMES` constant removed in previous fix, was dead type-level code
- `agira/orchestrator/engine.py`: `_determine_success()` — complex nested validation logic with multiple early returns, hard to follow

## 6. PERFORMANCE BOTTLENECKS

1. **`syncHistoryFromJobs()`** — O(n) filesystem reads per history request
2. **`MemoryStore._save()`** — synchronous disk write on every memory record
3. **`framer-motion`** — heavy JS bundle for mostly CSS-level animations
4. **Polling every 1500ms** — no backoff, potential thundering herd
5. **`lucide-react`** — full bundle imported, no per-icon tree-shaking

## 7. SECURITY RISKS

| Risk | Severity | Detail |
|------|----------|--------|
| No API authentication | 🔴 CRITICAL | All 5 routes unprotected |
| Arbitrary path read | 🔴 CRITICAL | `resolveRepoPath` accepts absolute paths |
| GitHub clone stub | 🔴 CRITICAL | Users can't use real GitHub URLs |
| `AGIRA_JOBS_DIR` env var | 🟡 HIGH | If overridden, could write anywhere |
| `MEMORY_STORE_PATH` uses `~/.agira` | 🟡 HIGH | Default path is user home dir |
| Python `job_runner.py` spawn | 🟡 HIGH | `spawn(PYTHON_BIN, [runner, jobDir, repoPath])` — repo path from user input |
| No input validation on `job_id` | 🟡 HIGH | Query param passed directly to `readFileSync` |
| `SETTINGS_PATH` via `process.cwd()` | 🟢 LOW | Working directory controllable |

## 8. UX PROBLEMS

1. Theme toggle MISSING from app navigation (NavBar non-landing mode)
2. Dark mode completely broken on all app pages (C-1)
3. MetricsSection broken in light mode (H-1)
4. No loading skeletons — only Suspense fallback text "Loading…"
5. No error boundaries — errors produce blank screens
6. RepositoryUploader GitHub URL mode is non-functional
7. Demo mode (`?demo`) auto-triggers analysis but provides no feedback during the long-running job
8. Settings toggle for `adaptive_planning` is missing from the UI
9. No `skip-to-content` link for keyboard/screen reader users
10. MetricsSection (`bg-foreground text-background`) is visually jarring — a stark black section in the middle of the page

---

## BUILD & TEST STATUS

| Check | Result |
|-------|--------|
| `npm run build` | ✅ PASSES |
| `npm run lint` | ⚠️ 1 error, 1 warning (pre-existing) |
| `pytest` | ⚠️ 10 pass, 1 FAIL (`test_bug_hunter_finds_issues`) |

---

## REMAINING RISKS

1. App pages will remain visually broken in dark mode until all components are migrated to CSS variable tokens
2. Demo flow (GitHub URL analysis) is non-functional — only local paths work
3. Backend has no test coverage (only `test_subagents.py` exists, and it fails)
4. No authentication means the system cannot be safely exposed
5. Path traversal means the system cannot safely analyze user-provided repos