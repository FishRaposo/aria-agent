import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import SkillsView from "@/components/SkillsView";
import { mockBackendDown } from "../utils";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SkillsView", () => {
  it("renders activated and closed skills when offline", async () => {
    mockBackendDown();
    render(<SkillsView />);
    await waitFor(() =>
      expect(screen.getByTestId("skills-view")).toBeInTheDocument()
    );
    expect(screen.getAllByText("calculator").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Instructions withheld/).length).toBeGreaterThan(0);
    expect(screen.getByText("release-notes")).toBeInTheDocument();
  });
});
