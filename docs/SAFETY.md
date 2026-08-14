# Safety policy

`ARIA_SAFETY_MODE` accepts `off`, `warn`, or `block` and defaults to `warn`.
The classifier is intentionally deterministic and conservative: it recognizes
common instruction-override patterns in queries, context, and arguments. A
warning is traced; a block returns a structured blocked result without routing.
It is not a substitute for deployment policy or human review.
