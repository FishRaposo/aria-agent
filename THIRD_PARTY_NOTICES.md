# Third-party notices

## Internally vendored operator core subset

ARIA contains a narrow, internally namespaced copy of the modules it uses from
`FishRaposo/operator-shared-core` v1.3.0. The source is pinned to commit
`dbf276a7708da65b55e1f10b35af634b300d1f07` and lives under
`src/aria/internal/vendor_core/`.

The vendored modules remain under their original MIT license. The rest of ARIA
does not require, install, or import an external `shared_core` package. The
vendored subset is implementation detail; public ARIA imports remain under the
`aria` namespace.

Copyright (c) 2026 Vinícius Raposo

