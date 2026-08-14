# Streaming

`POST /agent/chat/stream` returns Server-Sent Events. Each event includes a
monotonic sequence and JSON payload. Event types are `reasoning`, `decision`,
`approval`, `tool`, `error`, and `complete`. The stream uses the same engine as
`POST /agent/chat`; clients should not infer a second result schema.
