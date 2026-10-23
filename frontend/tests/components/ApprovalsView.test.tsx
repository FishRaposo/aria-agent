import { resetDemo } from "@/lib/demo-scenarios";
import { MOCK_APPROVALS } from "@/lib/mockData";
import { mockHttpOk } from "../utils";
import { setProviderMode } from "@/lib/demo-scenarios";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ApprovalsView from "@/components/ApprovalsView";
import { mockBackendDown } from "../utils";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ApprovalsView", () => {
  it("renders the approval queue with pending actions when offline", async () => {
    setProviderMode("sample");
    mockBackendDown();
    render(<ApprovalsView />);
    await waitFor(() =>
      expect(screen.getByTestId("approval-list")).toBeInTheDocument()
    );
    expect(screen.getAllByText("email_draft").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Approve").length).toBeGreaterThan(0);
  });

  it("approves a pending item and shows a not-persisted demo notice", async () => {
    setProviderMode("sample");
    mockBackendDown();
    render(<ApprovalsView />);
    await waitFor(() => screen.getByTestId("approval-list"));
    fireEvent.click(screen.getAllByText("Approve")[0]);
    await waitFor(() =>
      expect(screen.getByText(/not persisted/i)).toBeInTheDocument()
    );
  });
});


describe("authoritative approval outcomes", () => {
  it.each([["claimed", "Execution claimed; outcome unconfirmed"], ["failed", "Execution failed"], ["completed", "Execution completed"], [null, "Execution unconfirmed"]])("labels connected %s execution without claiming simulation", async (execution_status, label) => {
    mockHttpOk({ approvals: [{ ...MOCK_APPROVALS[0], status: "approved", execution_status }] });
    render(<ApprovalsView />);
    await waitFor(() => expect(screen.getByTestId("approval-list")).toBeInTheDocument());
    expect(screen.getByText(label as string)).toBeInTheDocument();
    expect(screen.queryByText("Simulated once")).not.toBeInTheDocument();
  });
  it("reports expiry returned during an approve request without a success notice", async () => {
    setProviderMode("sample"); resetDemo();
    render(<ApprovalsView />);
    await waitFor(() => screen.getByTestId("approval-list"));
    const now = Date.now(); vi.spyOn(Date, "now").mockReturnValue(now + 240_001);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Expired. Not executed."));
    expect(screen.queryByText(/Approved unchanged action/)).not.toBeInTheDocument();
  });
});
