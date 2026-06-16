import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import CostSummaryCard from "@/components/CostSummaryCard";
import { MOCK_RUNS } from "@/lib/mockData";

describe("CostSummaryCard", () => {
  it("renders cost, tokens, calls, and latency labels", () => {
    render(<CostSummaryCard cost={MOCK_RUNS[1].cost} />);
    expect(screen.getByText("Cost")).toBeInTheDocument();
    expect(screen.getByText("Tokens")).toBeInTheDocument();
    expect(screen.getByText("LLM calls")).toBeInTheDocument();
    expect(screen.getByText("Avg latency")).toBeInTheDocument();
  });

  it("formats the cost as USD", () => {
    render(<CostSummaryCard cost={MOCK_RUNS[1].cost} />);
    // run e5f6a7b8 has estimated_cost 0.00318
    expect(screen.getByText("$0.00318")).toBeInTheDocument();
  });
});
