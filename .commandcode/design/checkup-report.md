# Checkup — ARIA Agent

**Date:** 2026-11-08  
**Mode:** checkup  
**Scope:** landing, `/runs`, `/chat`, `/skills`, `/tools`, `/approvals`, `/memory`, `/setup`; static production export at 390 and 1440.  
**Register:** Brand landing + product console.  
**Evidence:** static export under `/aria-demo`; axe WCAG 2A/AA; Playwright 21/21; 64 Vitest tests; LCP/CLS; target/heading/overflow measurements.

## Verdict

**APPROVE — 60/60.** The landing and every console route have one h1, no axe violations, no horizontal overflow, no sub-44px controls and no text below 12px. The graphite-and-amber control-room system replaces the generic indigo console.

## Score

| # | Vital | Status | Score | Evidence |
|---|---|---|---|---|
| 1 | Intentionality | Healthy | 10/10 | Safety-amber on warm graphite; execution record carries the hero; no AI gradient/glow. |
| 2 | Readability | Healthy | 10/10 | 12px+ labels, 16px mobile controls, clear h1/h2 hierarchy, axe-clean contrast. |
| 3 | Usability | Healthy | 10/10 | Guided demo, story routes, named nav, filters and approvals work at all widths. |
| 4 | Responsiveness | Healthy | 10/10 | Eight routes at 390/1440; no overflow; 44px nav; wordmark collapses to the mark. |
| 5 | Speed | Healthy | 10/10 | Static export LCP 484ms desktop / 240ms mobile; CLS 0; 10 requests. |
| 6 | Accessibility | Healthy | 10/10 | Axe 0 every route; skip link; nav names; focusable scroll regions; 44px actions; axe a11y suite. |
| | **Total** | | **60/60** | No open findings. |

## Composition and prompt fidelity

The landing names controlled execution, then shows the execution record at the center: request, validated tool, human-approval boundary, and "no approval, no execution." The three stories are distinct outcomes, not generic feature cards. The console keeps the same boundary language in runs, approvals, skills, tools, memory and setup. The name, user pressure, artifact and evidence survive a swap test.

## Findings

**No open findings.** Resolved:

| # | Severity | Discipline | Location | Before | After | Why |
|---|---|---|---|---|---|---|
| 1 | HIGH | Color | Tailwind brand/ink + globals | Indigo/violet AI palette and slate text | Graphite/amber control-room palette | The category reflex obscured the execution-boundary story |
| 2 | HIGH | Accessibility | `globals.css` / nav | Nav links and toolbar actions 16–32px | 44px nav, toolbar, button and filter targets | Touch and keyboard users missed small actions |
| 3 | HIGH | Accessibility | `setup/page.tsx` | Scrollable code blocks unfocusable | `tabIndex=0` on scrollable pre blocks | Keyboard users could not scroll the setup commands |
| 4 | HIGH | Accessibility | `Nav.tsx` | Brand aria-label omitted visible text | Removed the redundant label; visible name stands | `label-content-name-mismatch` failed axe |
| 5 | MEDIUM | Typography | globals + TSX | 9–11px labels throughout | 12px minimum technical labels | Dense labels were unreadable |
| 6 | MEDIUM | Responsiveness | `Nav.tsx` | 44px nav links plus wordmark overflowed 390px | Wordmark collapses to the brand mark below sm; nav fits | Touch targets and viewport both matter |
| 7 | MEDIUM | Interaction | Skills/tools/approvals | Disclosure links and native pre blocks were tiny/unfocusable | 44px disclosures, focusable scroll regions | Operate surfaces need visible, operable detail |
| 8 | LOW | Motion | Nav/globals | Backdrop blur and old motion default | Solid header; reduced-motion rule preserved | Remove unearned depth and respect motion preference |

## Considered but rejected

| Location | Candidate | Rejected because |
|---|---|---|
| Landing | Replace story cards with a table | The three outcomes are a narrative; the cards are distinct, linked stories |
| Console | Light paper theme | The execution console is a dark instrument; graphite/amber keeps the boundary visible |
| Inline chat suggestions | Remove the sentence links | They are useful shortcuts; they are now 44px inline targets |
| Brand | Custom display face | The control-room voice comes from the execution record, palette and mono labels; plain sans is appropriate |

## Verification

**Run:** static export under `/aria-demo`; eight routes at 390/1440; axe every route; Playwright 21/21 including the a11y suite; Vitest 64/64; lint; build; target/heading/overflow; LCP/CLS. **Observed:** axe 0, one h1 per route, no overflow, zero small targets, zero <12px text, CLS 0. **Not verified:** live Pages latency after deployment; a real screen-reader session.

## Next modes

No in-product work remains. Keep the execution record and boundary language as the shared composition for new console views.
