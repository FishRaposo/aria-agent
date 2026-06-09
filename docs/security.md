# Security Boundaries & Rules - Aria Agent

This document outlines the security parameters, trust boundaries, and execution guardrails enforced by the Aria Agent.

---

## 1. Tool Execution & Directory Sandboxing

- **Strict Schema Validation**: Tool arguments are defined and validated via Pydantic model definitions in the `ToolRegistry`. Unstructured, dynamic tool payloads must be rejected prior to execution.
- **Directory Restrictions**: Any file-operations tool (e.g., `file_reader`, `file_writer`) must restrict read/write access to a designated sandbox folder. File paths containing traversal sequences (`..`) must trigger validation failures.
- **No Shell Execution**: The core tool configuration must exclude arbitrary shell execution layers. Tools invoking system commands must lock command arguments to predefined templates.

---

## 2. Human Approval Gates (HITL)

- **Categorized Tool Risk Levels**: Tools are classified into risk bands:
  - *Low Risk* (e.g., calculations, lookup metrics): Executed automatically.
  - *High Risk* (e.g., writing files, sending notifications, database edits): Requires human validation.
- **State Suspension**: When a high-risk tool is triggered, the agent session state changes to `PENDING_APPROVAL`, pausing loop execution until approved.
- **No Automated Bypasses**: Bypassing approval gates via LLM instructions is blocked at the code interface level.

---

## 3. Prompt Injection Defense

- **Separation of Instructions & Context**: The system prompt enforces role boundaries, instructing the agent to treat observations as untrusted data inputs.
- **Input Sanitization**: Variables passed into LLM completions must be stripped of instruction tags (such as `system:`, `user:`, `assistant:`, or markdown delimiters that mock model formats).
- **Execution Budgeting**: Guarding against injection-triggered infinite loops by enforcing rigid execution timeouts and loop iteration limits.

---

## 4. Audit Logging

- **Immutable Trace Logs**: Trace records of prompt runs, tool invocations, inputs, and observation responses must be captured to persistent, append-only logs for developer audit.
- **Sanitized Observations**: Trace logs must strip active tokens, credentials, or PII before writing.
