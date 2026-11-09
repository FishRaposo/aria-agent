# Design system — ARIA Agent

**Register:** Brand landing + product console. **Direction:** graphite-and-amber control room.

## Tokens

| Role | Value |
|---|---|
| Canvas | `#0e0f0c` |
| Surface | `#171712` / `#10110d` |
| Ink | `#f6f4ef` |
| Secondary | `#d8d2c6` |
| Muted | `#a69e8e` |
| Amber accent | `#d3953f` |
| Amber action | `#9a6122` |
| Deep amber | `#7a4a1c` |
| Status | emerald completed, amber review, rose denied/error |
| Focus | `#efcf95` |
| Border | `#3a362b` |

**Type:** system/Arial reading sans; mono for execution IDs, JSON and labels. Labels minimum 12px; mobile form controls 16px; h1 41–60px landing, 24px console.

## Composition

- Landing: two-column hero with execution record; three linked outcome stories.
- Console: sticky nav with 44px links; sample/connected toolbar; one h1 per route; evidence-first pages.
- Record: request → proposed tool → human-approval boundary → no-approval/no-execution footer.
- Approvals: named filters, parameters, approve/reject.
- Setup: copyable commands, focusable code panes.

## Interaction and access

44px nav/action/filter targets; 44px inline chat suggestions; focusable scrollable pre blocks; skip link; visible focus; mobile wordmark collapses to the mark; reduced-motion rule; `aria-live` notices; no color-only state.

## Module record

| Module | Result |
|---|---|
| setup | Brief with user, job, artifact, evidence, refused drift. |
| checkup | 60/60. |
| smell | 10/10. |
| review | 50/50. |
| deslop | Removed indigo, glow, blur and tiny-label style. |
| typeset | 12px+ labels; 16px mobile controls. |
| recolor | Graphite/amber control-room palette. |
| motion | Reduced-motion rule; no decorative motion. |
| interaction | Navigation, disclosures, filters, inline prompts at 44px. |
| a11y | Axe 0; one h1; named controls; focusable scroll regions. |
| relayout | Execution record hero; responsive nav mark. |
| responsive | Eight routes at 390/1440, no overflow. |
| tokenize | brand/ink scales and shared button/nav classes. |
| finish | Lint, build, 64 Vitest, 21 Playwright, LCP/CLS. |
| refine | Control instrument with a human boundary. |
| voice | Explicit, inspectable, non-anthropomorphic. |
| surface | Landing, console, sample/connected toolbar, approvals, setup. |
| redesign | Applied to palette, landing artifact and target system. |

## Evidence map

`frontend/tailwind.config.ts`, `src/app/globals.css`, `src/components/Nav.tsx`, `src/components/DemoShell.tsx`, `src/components/ChatPanel.tsx`, `src/components/ApprovalsView.tsx`, `src/components/SkillsView.tsx`, `src/components/ToolsView.tsx`, `src/app/setup/page.tsx`, `.commandcode/design/*`.
