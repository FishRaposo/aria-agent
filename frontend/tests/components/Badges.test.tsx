import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  ApprovalStatusBadge,
  ModeBadge,
  PermissionBadge,
  StatusBadge,
} from "@/components/Badges";

describe("Badges", () => {
  it("renders run status labels", () => {
    render(<StatusBadge status="pending_approval" />);
    expect(screen.getByText("Pending approval")).toBeInTheDocument();
  });

  it("renders safe vs requires-approval permissions", () => {
    const { rerender } = render(<PermissionBadge permission="safe" />);
    expect(screen.getByText("Safe")).toBeInTheDocument();
    rerender(<PermissionBadge permission="requires_approval" />);
    expect(screen.getByText("Requires approval")).toBeInTheDocument();
  });

  it("renders approval status capitalized", () => {
    render(<ApprovalStatusBadge status="approved" />);
    expect(screen.getByText("approved")).toBeInTheDocument();
  });

  it("renders agent mode", () => {
    render(<ModeBadge mode="approval_gated" />);
    expect(screen.getByText("approval-gated")).toBeInTheDocument();
  });
});
