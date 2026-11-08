# Portfolio images

Three 1000×750 cards for ARIA, built from the repository's own captures — one sample run, one denial,
one connected run.

| File | What it shows | Source |
|---|---|---|
| `aria-01-cover.png` | The approval boundary: run `c9d0e1f2`, `email_draft`, pending review, 0 executions | `docs/images/portfolio-approval.png` |
| `aria-02-denied.png` | Repository text asking for `email_send`; the tool is unregistered, so nothing runs | `docs/images/portfolio-denied.png` |
| `aria-03-connected.png` | The same gate against a connected backend | `docs/images/connected-completed.png` |

**What the cards claim, and what they do not.** The approval binds one run and the exact arguments a
reviewer saw — the screen says so, and the run record shows `0 executions` before approval. The
denial card shows the mechanism failing closed: `email_send` is not a registered tool, so there is no
execution, no model call and no side effect. Neither card is a security proof: they demonstrate the
gate's behaviour, not that every path is closed.

**Provenance.** Crops come from the repository captures at their native size, cut at a whitespace
boundary rather than by eye, laid out 1000×750 and downscaled with Lanczos. The sample mode is
tab-local with no backend calls; the third card is the connected capture, and its timings are not a
benchmark.
