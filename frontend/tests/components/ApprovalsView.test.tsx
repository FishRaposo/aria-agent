import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ApprovalsView from "@/components/ApprovalsView";
import { mockBackendDown } from "../utils";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ApprovalsView", () => {
  it("renders the approval queue with pending actions when offline", async () => {
    mockBackendDown();
    render(<ApprovalsView />);
    await waitFor(() =>
      expect(screen.getByTestId("approval-list")).toBeInTheDocument()
    );
    expect(screen.getAllByText("email_draft").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Approve").length).toBeGreaterThan(0);
  });

  it("approves a pending item and shows a not-persisted demo notice", async () => {
    mockBackendDown();
    render(<ApprovalsView />);
    await waitFor(() => screen.getByTestId("approval-list"));
    fireEvent.click(screen.getAllByText("Approve")[0]);
    await waitFor(() =>
      expect(screen.getByText(/not persisted/i)).toBeInTheDocument()
    );
  });
});
