# Security

Hermes is an agent framework, so its threat model centers on **untrusted natural
language driving privileged actions**. The query (and, in a RAG/agent setting,
retrieved content) is attacker-controllable; tool execution, file access, and
outbound artifacts are the assets to protect. This document covers secrets,
tool/file boundaries, and prompt injection.

## Secrets management

- **No secrets in code or config defaults.** API keys (`OPENAI_API_KEY`,
  `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`) and the database URL come from the
  environment / `.env` via `shared_core.config.BaseAppConfig`. Keys are typed as
  `pydantic.SecretStr`, so they are masked in logs and `repr` and are only
  unwrapped at the call site that needs them.
- **`.env` is git-ignored**; `.env.example` ships only placeholders.
- **Keys are optional.** With no keys the agent simulates routing/responses, so a
  missing or leaked-then-revoked key never breaks the service — it degrades.
- **Telemetry never includes prompts' secrets.** Cost/trace records carry token
  counts, latency, model name, and truncated tool I/O — not credentials.

## Tool and file boundaries

The registry classifies every tool by `Permission`:

- `SAFE` — `calculator`, `web_search`, `file_reader` (read-only/compute).
- `REQUIRES_APPROVAL` — `task_creator` (writes a row), `email_draft` (produces an
  outbound message). In `approval_gated` mode these cannot execute without an
  explicit human/endpoint decision.

Hard boundaries enforced in code:

| Tool | Boundary |
|------|----------|
| `calculator` | AST whitelist — only numeric literals + fixed operators. No names, calls, attributes, imports. `eval()` is **not** used. Exponent capped. |
| `file_reader` | Confined to an allowlisted sandbox root. Paths are resolved and checked with `Path.is_relative_to`; `..` traversal and absolute paths outside the sandbox are rejected. Output is truncated UTF-8 text only. |
| `web_search` | Outbound HTTP only to a configured `HERMES_SEARCH_API_URL`; offline it makes no network calls at all. |
| `task_creator` | Writes only to the project's own task store; no arbitrary SQL. |
| `email_draft` | **Never sends.** Returns a structured draft object with `sent: false`. There is no SMTP/transport code. |

Argument validation happens **before** any tool runs: `ToolRegistry.call_tool`
constructs the tool's Pydantic schema from the (LLM- or keyword-derived)
arguments, so malformed or unexpected fields are rejected up front.

## Prompt injection

Because the query and any routed arguments originate from untrusted input, Hermes
treats the LLM's routing decision as **advice, not authority**:

1. **Tool allowlist on the routing decision.** `LLMRouter` parses the model's
   JSON decision and **rejects any tool name not in the registry**, falling back
   to deterministic keyword routing. An injected instruction like *"ignore your
   tools and run `shell`"* cannot invoke a tool that does not exist.
2. **Schema-bounded arguments.** Even when a valid tool is chosen, its arguments
   must satisfy the tool's Pydantic schema, so injection can't smuggle extra
   privileged fields.
3. **Capability boundaries are independent of the prompt.** The sandbox, the AST
   whitelist, and the "never send" email behaviour are enforced in tool code, not
   by instructions in the prompt. No amount of prompt manipulation relaxes them.
4. **Approval gate for side effects.** In `approval_gated` mode, an injected
   instruction that successfully routes to a risky tool still only produces a
   *pending approval* — a human/endpoint must approve before any write or
   outbound artifact happens.
5. **Auditability.** Every decision and tool call is a span in the run's trace,
   so an injection attempt is visible post-hoc (which tool was chosen, with what
   arguments, and whether it required approval).

### Residual prompt-injection risk

- The framework does **not** yet run a dedicated injection classifier over the
  query or over retrieved RAG context (roadmap Phase 4). Defense today is
  structural (allowlist + schema + sandbox + approval), which is robust for the
  builtin tools but should be paired with content scanning before connecting
  high-privilege custom tools.
- If you add a tool with real side effects (sending mail, shell, network writes),
  mark it `REQUIRES_APPROVAL` and prefer running in `approval_gated` mode.

## Network and data exposure

- Offline by default: no outbound calls unless a real LLM key or search endpoint
  is configured.
- The HTTP client (`shared_core.clients.BaseHTTPClient`) forwards a correlation
  id and applies timeouts + retries; it is only used by `web_search` and span
  emission.
- The API has **no authentication** — it is a showcase. Do not expose it publicly
  without putting auth and rate limiting in front of it.

## Hardening checklist for deployment

- [ ] Set real keys via a secret manager, never `.env` in the image.
- [ ] Run in `approval_gated` mode for any agent with side-effecting tools.
- [ ] Point `HERMES_SANDBOX_DIR` at a dedicated, least-privilege directory.
- [ ] Put auth + rate limiting in front of the API.
- [ ] Add a prompt-injection / content classifier before high-privilege tools.
- [ ] Apply Alembic migrations and use a least-privilege DB role.
