# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-06-26
- Primary product surfaces: `apps/gmp_pageindex_ui.py` Streamlit dashboard for v0.1 document exploration and v0.2 evaluation analysis.
- Evidence reviewed:
  - `README.md` GMP PageIndex Local UI section documents local/offline use and score semantics.
  - `.omx/plans/ralplan-pageindex-ui-v03-20260626.md` defines the local-first UI contract, canonical 0.96 score rule, and v0.1/v0.2/v0.3 boundaries.
  - `apps/gmp_pageindex_ui.py` is the current Streamlit shell.
  - `pageindex/ui_contracts.py` and `pageindex/ui_data.py` provide typed view objects and artifact loaders.
  - `scripts/gmp_pageindex_ui_smoke.py` verifies score semantics and artifact readiness.

## Brand
- Personality: calm, expert, presentation-ready, evidence-first.
- Trust signals: explicit local/offline badge, canonical score labeling, unresolved item visibility, source artifact paths, physical/internal page labels.
- Avoid: flashy gradients, oversized emoji, dense debug-first JSON, ambiguous score naming, any UI that makes diagnostic 0.99 look like the official score.

## Product goals
- Goals:
  - Let a presenter explain the GMP PageIndex pipeline clearly from document tree to eval evidence.
  - Make v0.1 document exploration and v0.2 retrieval/eval analysis look polished enough for demo and stakeholder review.
  - Preserve the canonical 0.96 vs diagnostic 0.99 distinction.
- Non-goals:
  - Do not expose v0.3 runner controls in the presentation UI.
  - Do not mutate canonical artifacts or run remote model/API calls from the default UI.
  - Do not replace the Python/PageIndex pipeline with a separate frontend stack.
- Success signals: the main screen communicates corpus, score, and unresolved status at a glance; users can locate tree/page/eval evidence without reading raw files.

## Personas and jobs
- Primary personas:
  - Builder/researcher validating PageIndex retrieval behavior.
  - Non-technical or semi-technical reviewer watching a product demo.
- User jobs:
  - Search a GMP question and see likely section/page evidence.
  - Inspect a 100-question eval row and understand hit/miss classification.
  - Explain why the official metric is 0.96 and what diagnostic 0.99 means.
- Key contexts of use: local laptop demo, internal progress review, iterative QA over local artifacts.

## Information architecture
- Primary navigation: two top-level tabs only: `v0.1 문서 탐색`, `v0.2 Eval 분석`.
- Core routes/screens: one Streamlit app with sidebar artifact settings and main dashboard panels.
- Content hierarchy: hero summary -> score cards -> tab-specific controls -> evidence cards/page text.

## Design principles
- Principle 1: Evidence before decoration; every visual element should help explain artifact-backed behavior.
- Principle 2: Quiet polish; use whitespace, cards, consistent labels, and restrained colors instead of flashy visual effects.
- Tradeoffs: Streamlit-native controls are acceptable for speed and reliability; custom HTML/CSS is used only for layout polish and semantic cards.

## Visual language
- Color: off-white background, navy/slate text, soft blue accent, green for pass/hit, amber/red for unresolved/miss.
- Typography: system sans-serif, clear hierarchy, compact Korean labels.
- Spacing/layout rhythm: card-based sections with 16-24px padding, generous gaps, no visual clutter.
- Shape/radius/elevation: 14-18px radius, subtle 1px borders, very light shadows.
- Motion: none.
- Imagery/iconography: minimal text badges and small status icons only when they improve scanning.

## Components
- Existing components to reuse: Streamlit sidebar, tabs, columns, metrics, expanders, select boxes, text inputs, text areas.
- New/changed components: HTML hero, score cards, insight cards, status badges, path chips, page candidate cards, eval summary table/cards.
- Variants and states: hit/miss/unresolved badges; canonical/diagnostic score variants; empty-search and no-result states.
- Token/component ownership: presentation CSS lives in `apps/gmp_pageindex_ui.py`; data contracts remain in `pageindex/ui_contracts.py` and `pageindex/ui_data.py`.

## Accessibility
- Target standard: pragmatic WCAG AA readability for local demo use.
- Keyboard/focus behavior: rely on Streamlit-native controls for focus and keyboard behavior.
- Contrast/readability: dark text on light background, colored badges with text labels not color alone.
- Screen-reader semantics: keep headings and labels textual; avoid icon-only meaning.
- Reduced motion and sensory considerations: no animations or auto-refreshing visual effects.

## Responsive behavior
- Supported breakpoints/devices: desktop/laptop first; usable on narrow browser widths with Streamlit column wrapping.
- Layout adaptations: key metrics collapse from columns; evidence panels remain readable as stacked sections.
- Touch/hover differences: no hover-only controls.

## Interaction states
- Loading: Streamlit default loading is acceptable.
- Empty: show plain-language Korean guidance when no tree/eval rows match.
- Error: fail closed with artifact path and readable error message.
- Success: use restrained green badges/metrics for hit states.
- Disabled: v0.3 controls are intentionally absent from the presentation UI.
- Offline/slow network, if applicable: default UI is local/offline; no network-dependent state.

## Content voice
- Tone: concise, professional, Korean-first with technical terms preserved where useful.
- Terminology: `Canonical 0.96`, `Diagnostic 0.99`, `physical page`, `internal label`, `aligned`, `evidence`.
- Microcopy rules: explain score semantics directly; avoid claiming a diagnostic metric is production accuracy.

## Implementation constraints
- Framework/styling system: Streamlit with small custom HTML/CSS blocks; no new frontend build system.
- Design-token constraints: keep colors/radius/shadow defined in one CSS block inside the app shell.
- Performance constraints: load existing local JSON/JSONL artifacts only; avoid expensive reprocessing during rendering.
- Compatibility constraints: preserve pure core modules with no Streamlit import; keep v0.3 runner implementation available but hidden from presentation UI.
- Test/screenshot expectations: run `scripts/gmp_pageindex_ui_smoke.py`, Python compile checks, and a headless Streamlit startup/smoke request before declaring complete.

## Open questions
- [ ] Whether a future static HTML export is needed for offline sharing without Streamlit / owner: product / impact: distribution packaging.
