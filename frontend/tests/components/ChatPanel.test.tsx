import { setProviderMode } from "@/lib/demo-scenarios";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatPanel from "@/components/ChatPanel";
import { mockBackendDown } from "../utils";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ChatPanel", () => {
  it("renders an empty prompt with example suggestions", () => {
    setProviderMode("sample");
    mockBackendDown();
    render(<ChatPanel />);
    expect(screen.getByTestId("chat-thread")).toBeInTheDocument();
    expect(screen.getByText(/Ask the agent something/i)).toBeInTheDocument();
  });

  it("runs a calculation turn locally in demo mode", async () => {
    setProviderMode("sample");
    mockBackendDown();
    render(<ChatPanel />);
    const box = screen.getByLabelText("Message the agent");
    fireEvent.change(box, { target: { value: "What is 1450 * 32?" } });
    fireEvent.click(screen.getByText("Send"));

    // user message echoes immediately
    expect(screen.getByTestId("chat-thread")).toHaveTextContent("What is 1450 * 32?");

    // agent reply + tool call render after the local loop resolves
    await waitFor(() =>
      expect(screen.getByText("calculator")).toBeInTheDocument()
    );
    expect(screen.getAllByTestId("demo-badge").length).toBeGreaterThan(0);
  });

  it("surfaces the approval gate for a write tool in approval-gated mode", async () => {
    setProviderMode("sample");
    mockBackendDown();
    render(<ChatPanel />);
    fireEvent.change(screen.getByLabelText("Mode"), {
      target: { value: "approval_gated" },
    });
    const box = screen.getByLabelText("Message the agent");
    fireEvent.change(box, {
      target: { value: "Draft an email to ops@example.test" },
    });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() =>
      expect(screen.getByText(/Held for approval/i)).toBeInTheDocument()
    );
  });
});

it("offers Retry and an explicit sample switch after connected chat failure", async () => {
  setProviderMode("connected");
  const fetchSpy = mockBackendDown();
  render(<ChatPanel />);
  fireEvent.change(screen.getByLabelText("Message the agent"), { target: { value: "What is 7 * 8?" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "Enter sample demo" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(fetchSpy.mock.calls.filter(call => String(call[0]).includes("/agent/chat"))).toHaveLength(2));
});
