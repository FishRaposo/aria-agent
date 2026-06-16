import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";

describe("State components", () => {
  it("renders a loading skeleton with the requested rows", () => {
    const { getByTestId } = render(<LoadingSkeleton rows={3} />);
    expect(getByTestId("loading-skeleton").children).toHaveLength(3);
  });

  it("renders an empty state", () => {
    render(<EmptyState title="Nothing here" message="Add some data." />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Add some data.")).toBeInTheDocument();
  });

  it("renders an error state and fires retry", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="It broke" onRetry={onRetry} />);
    expect(screen.getByText("It broke")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
