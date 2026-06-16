import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatPanel from "@/components/ChatPanel";
import { mockBackendDown } from "../utils";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ChatPanel", () => {
  it("renders an empty prompt with example suggestions", () => {
    mockBackendDown();
    render(<ChatPanel />);
    expect(screen.getByTestId("chat-thread")).toBeInTheDocument();
    expect(screen.getByText(/Ask the agent something/i)).toBeInTheDocument();
  });

  it("runs a calculation turn locally in demo mode", async () => {
    mockBackendDown();
    render(<ChatPanel />);
    const box = screen.getByLabelText("Message the agent");
    fireEvent.change(box, { target: { value: "What is 1450 * 32?" } });
    fireEvent.click(screen.getByText("Send"));

    // user message echoes immediately
    expect(screen.getByText("What is 1450 * 32?")).toBeInTheDocument();

    // agent reply + tool call render after the local loop resolves
    await waitFor(() =>
      expect(screen.getByText("calculator")).toBeInTheDocument()
    );
    expect(screen.getAllByTestId("demo-badge").length).toBeGreaterThan(0);
  });

  it("surfaces the approval gate for a write tool in approval-gated mode", async () => {
    mockBackendDown();
    render(<ChatPanel />);
    fireEvent.change(screen.getByLabelText("Mode"), {
      target: { value: "approval_gated" },
    });
    const box = screen.getByLabelText("Message the agent");
    fireEvent.change(box, {
      target: { value: "Draft an email to ops@hermes.dev" },
    });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() =>
      expect(screen.getByText(/Held for approval/i)).toBeInTheDocument()
    );
  });
});
