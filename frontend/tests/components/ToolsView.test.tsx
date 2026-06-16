import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ToolsView from "@/components/ToolsView";
import { mockBackendDown } from "../utils";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ToolsView", () => {
  it("lists the five builtin tools with permission badges", async () => {
    mockBackendDown();
    render(<ToolsView />);
    await waitFor(() =>
      expect(screen.getByTestId("tool-list")).toBeInTheDocument()
    );
    expect(screen.getByText("calculator")).toBeInTheDocument();
    expect(screen.getByText("email_draft")).toBeInTheDocument();
    // at least one "Requires approval" badge
    expect(screen.getAllByText("Requires approval").length).toBeGreaterThan(0);
  });

  it("reveals a tool's schema parameters on expand", async () => {
    mockBackendDown();
    render(<ToolsView />);
    await waitFor(() => screen.getByText("calculator"));
    const toggles = screen.getAllByText("Show schema");
    fireEvent.click(toggles[0]);
    expect(screen.getByText("expression")).toBeInTheDocument();
  });
});
