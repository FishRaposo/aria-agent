# Replay

`POST /agent/runs/{run_id}/replay` reads recorded trace tool entries. The body
is optional and `{ "dry_run": true }` is the default. Dry replay reports the
recorded steps and never calls a tool. Non-dry replay is an explicit opt-in and
should be placed behind the normal approval boundary before any risky action.
