import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import TraceTimeline from "@/components/TraceTimeline";
import { MOCK_RUNS } from "@/lib/mockData";

describe("TraceTimeline", () => {
  it("renders one row per non-root span", () => {
    const run = MOCK_RUNS[0]; // calculator run: root + route + tool
    render(<TraceTimeline trace={run.trace} />);
    const list = screen.getByTestId("trace-timeline");
    // root span is excluded; calculator run has 2 child spans
    expect(list.children).toHaveLength(run.trace.spans.length - 1);
  });

  it("shows the tool span name", () => {
    render(<TraceTimeline trace={MOCK_RUNS[0].trace} />);
    expect(screen.getByText("tool.calculator")).toBeInTheDocument();
  });

  it("expands span attributes on click", () => {
    render(<TraceTimeline trace={MOCK_RUNS[0].trace} />);
    fireEvent.click(screen.getByText("tool.calculator"));
    expect(screen.getByText(/"result": "46400"/)).toBeInTheDocument();
  });

  it("handles an empty span list gracefully", () => {
    render(
      <TraceTimeline
        trace={{
          trace_id: "t",
          total_steps: 0,
          duration_ms: 0,
          entries: [],
          spans: [],
        }}
      />
    );
    expect(screen.getByText(/No spans recorded/i)).toBeInTheDocument();
  });
});
