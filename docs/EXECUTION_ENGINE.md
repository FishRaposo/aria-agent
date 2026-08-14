# Execution engine

`AgentEngine` owns the reason/route/approve/act loop. `ExecutionPlan` is bounded
by `AGENT_MAX_STEPS`; single-step mode is the compatibility default. Safety is
assessed before routing and before each planned tool call. Rate limits and retry
policies are deterministic and injectable for tests. `RunEvent` is the shared
event envelope for normal and SSE runs.
