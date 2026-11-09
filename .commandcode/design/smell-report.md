# Smell — ARIA Agent

**Date:** 2026-11-08  
**Mode:** smell  
**Scope:** landing, console shell and all console routes.  
**Register:** Brand landing + product console.

## Verdict

**CLEAN — 10/10.** The indigo AI-console lane is gone. ARIA now uses a warm graphite surface with safety-amber signals, and the execution record is the visual idea rather than a gradient or icon grid.

## Score

| # | Odor | Score | Evidence |
|---|---|---|---|
| 1 | Tech gradient | 1 | No indigo/cyan gradient; solid amber accent. |
| 2 | Generic tech hue | 1 | Graphite/amber is tied to approval and control. |
| 3 | Feature tile grid | 1 | Three outcome stories and one execution record; no icon grid. |
| 4 | Accent rail | 1 | The approval boundary and status dots carry meaning. |
| 5 | Unearned blur | 1 | Header blur removed; solid surfaces. |
| 6 | Stat monument | 1 | No oversized metric cluster; the execution record is the hero. |
| 7 | Icon topper | 1 | Icons label actions/status; no decorative section tops. |
| 8 | Bounce everywhere | 1 | Reduced-motion rule; restrained transitions. |
| 9 | Default type | 1 | Mono labels + plain sans are intentional for a control console. |
| 10 | Center stack | 1 | Asymmetric two-column hero and artifact. |
| | **Total** | **10/10** | No confirmed tells. |

## What is working

- The hero is a real execution record: request → validated tool → approval boundary → no approval, no execution.
- The three story cards are distinct outcomes (safe, needs approval, denied), not generic benefits.
- The graphite/amber palette and mono labels feel like an operating instrument.
- The console keeps the same decisions and language across runs, approvals, skills, tools and setup.
- The mobile shell is one disclosure-free horizontal nav with 44px targets and a collapsed wordmark.

## Considered but rejected

| Location | Candidate | Rejected because |
|---|---|---|
| Landing | Replace cards with a single hero | The three outcome stories teach the boundary; they are specific and linked |
| Console | Light theme | The console is an instrument; the dark surface supports trace scanning |
| Palette | Use green for the primary accent | Amber is the approval signal; green already means completed |

## Verification

Rendered all routes; computed palette/type/targets; axe every route; Playwright a11y suite; no open tell. Not verified: live stranger reaction.
