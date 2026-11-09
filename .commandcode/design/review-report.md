# Review — ARIA Agent

**Date:** 2026-11-08  
**Mode:** review  
**Scope:** landing, console shell and all eight routes.  
**Register:** Brand landing + product console.  
**Evidence:** static production export; Playwright 21/21; axe every route; Vitest 64/64; LCP/CLS; target/heading/overflow.

## Verdict

**SHIP — 50/50.** ARIA now looks and behaves like a controlled execution instrument. The promise, the record, the approval boundary and the console evidence are visible and operable; no open design findings.

## First impression

The landing names the category in the eyebrow, makes "An agent you can inspect and control" the h1, and puts a real execution record beside it. The record shows a validated tool, a human approval boundary and "No approval. No execution." The graphite/amber surface is specific and calm.

## Walkthrough

- **Landing:** two-column hero with execution record → three outcome stories → footer.
- **Console:** sticky nav with 44px links; connected/sample toolbar; one h1 per route; dense evidence with 12px+ labels.
- **Runs:** run list and charts; trace timeline and decision story remain inspectable.
- **Chat:** fixture prompts, mode select, inline suggestions and one clear execution boundary.
- **Skills/tools:** disclosures reach details without tiny targets; code panes are focusable.
- **Approvals:** named filters, exact action parameters, approve/reject controls at 44px.
- **Setup:** copyable commands, focusable scroll regions, and an explicit local runtime path.
- **Responsive:** 390/1440 no overflow; 44px nav; wordmark collapses below sm.

## Score

| Lens | Score | Evidence |
|---|---|---|
| First impression | 10/10 | Execution record, controlled-agent claim, graphite/amber. |
| Hierarchy | 10/10 | Hero claim → record → outcomes; one h1 per console route. |
| Color voice | 10/10 | Graphite/amber with semantic status colors; axe 0. |
| Type voice | 10/10 | Mono labels and system sans; 12px+ labels; 16px controls. |
| Interaction feel | 10/10 | 44px actions, focusable scroll regions, guided demo, approvals. |
| **Total** | | **50/50** |

## What would move the score

No open lens has a move. The surface is complete at 50/50.

## Findings

**No open findings.** Resolved: indigo/slate palette, tiny labels and targets, mobile nav overflow, unfocusable setup/skills/approval code panes, and the brand accessible-name mismatch.

## Considered but rejected

| Location | Candidate | Rejected because |
|---|---|---|
| Landing | Remove the three story cards | They are the three outcome states the console proves |
| Console | Add a second navigation pattern | One clear nav + mobile mark keeps the shell predictable |
| Chat inline suggestions | Leave them at text height | They are now 44px inline controls; no lost affordance |

## Verification

**Run:** static export under `/aria-demo`; eight routes at 390/1440; axe every route; Playwright 21/21; Vitest 64/64; lint; build; LCP 484/240ms; CLS 0. **Not verified:** live Pages latency and screen-reader session.

## Top recommendations

1. Ship; no design mode remains.
2. Reuse the execution-record block and boundary language for console additions.
3. Refresh any old indigo screenshots still used in external cards.
