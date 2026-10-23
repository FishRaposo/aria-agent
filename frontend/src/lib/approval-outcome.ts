import type { Approval, ApprovalDecisionResponse } from "@/types";
/** Approval is a permission decision. Execution has its own authoritative state. */
export function executionLabel(approval: Approval, sample: boolean): string {
  if (approval.status === "pending") return "Awaiting decision";
  if (approval.status !== "approved") return "Not executed";
  if (approval.execution_status === "completed") return sample ? "Simulated once" : "Execution completed";
  if (approval.execution_status === "claimed") return "Execution claimed; outcome unconfirmed";
  if (approval.execution_status === "failed") return "Execution failed";
  return "Execution unconfirmed";
}
export function decisionNotice(response: ApprovalDecisionResponse, sample: boolean): string {
  const approval = response.approval;
  if (approval.status === "expired") return "Expired. Not executed. Request a new review.";
  if (approval.status === "rejected") return "Rejected. Not executed.";
  if (approval.status === "pending") return "Still awaiting review. Not executed.";
  const execution = executionLabel(approval, sample);
  if (execution === "Simulated once") return "Approved unchanged action. Simulated exactly once; not persisted. No message sent.";
  if (approval.execution_status === "claimed") return "Approved. Execution claimed; outcome unconfirmed. Reconcile the outcome before requesting a fresh review.";
  return `Approved. ${execution}.${approval.execution_status === "completed" && response.result ? ` ${response.result}` : ""}`;
}
