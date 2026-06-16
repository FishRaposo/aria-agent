import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import RunsView from "@/components/RunsView";
import { mockBackendDown, mockHttpError } from "../utils";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RunsView", () => {
  it("renders bundled runs and a Demo mode badge when offline", async () => {
    mockBackendDown();
    render(<RunsView />);
    await waitFor(() =>
      expect(screen.getByTestId("run-list")).toBeInTheDocument()
    );
    expect(screen.getAllByTestId("demo-badge").length).toBeGreaterThan(0);
    // calculator run query appears
    expect(screen.getByText("What is 1450 * 32?")).toBeInTheDocument();
  });

  it("renders cost and latency charts", async () => {
    mockBackendDown();
    render(<RunsView />);
    await waitFor(() =>
      expect(screen.getByTestId("cost-chart")).toBeInTheDocument()
    );
    expect(screen.getByTestId("latency-chart")).toBeInTheDocument();
  });

  it("shows an error state on a real HTTP error", async () => {
    mockHttpError(500, "kaboom");
    render(<RunsView />);
    await waitFor(() =>
      expect(screen.getByTestId("error-state")).toBeInTheDocument()
    );
    expect(screen.getByText(/kaboom/)).toBeInTheDocument();
  });
});
