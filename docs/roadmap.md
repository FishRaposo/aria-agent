# Project Roadmap - Aria Agent

This document outlines the milestones and trajectory of the Aria Agent (ARIA — Agentic Reasoning & Integration Architecture).

---

## Milestone 1: Agent Execution Core (Completed)
- **Tool Registry**: Validate schema definitions dynamically using Pydantic models.
- **State and Memory Store**: Maintain system and user prompt states within memory-buffered conversation sessions.
- **Trace Logger**: Log tool invocations, inputs, and outputs per iteration.
- **Human-in-the-Loop Hooks**: Code scaffolds for interrupting execution to await human approval.

---

## Milestone 2: Run Inspectability & Budget Limits (Planned)
- **Visual Run Inspector**: A web-based timeline interface to inspect agent execution traces, detailing prompts, tool calls, and observations.
- **Approval Queue Dashboard**: A central console for administrators to approve, modify, or reject pending agent actions.
- **Strict Budget Controls**: Configure hard dollar limits (e.g., max `$0.50` per task) and token quotas that halt execution if breached.
- **Session State Database**: Move conversation state from volatile RAM to a PostgreSQL schema, enabling runs to pause and resume across restarts.

---

## Milestone 3: Secure Sandbox & Multi-Agent Collaboration (Future)
- **Safe Execution Sandbox**: Execute AI-generated code snippets in highly secure, isolated micro-containers (Docker or WebAssembly) rather than host processes.
- **Vector-Based Episodic Memory**: Integrate semantic retrieval of past conversation traces to allow agents to learn from historical runs.
- **Tool Access Control (RBAC)**: Bind tool permissions to user authorization levels, preventing unauthorized tool execution.
- **Hierarchical Multi-Agent Workflows**: Support orchestrator-worker layouts where supervisor agents delegate sub-tasks to specialized worker agents.
