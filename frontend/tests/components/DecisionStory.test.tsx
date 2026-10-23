import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import DecisionStory from "@/components/DecisionStory";
import { getDemoState, resetDemo, setProviderMode } from "@/lib/demo-scenarios";
afterEach(() => vi.restoreAllMocks());
it("describes the returned expired decision when approval crosses its deadline", async () => {
  setProviderMode("sample"); resetDemo();
  render(<DecisionStory run={getDemoState().runs[1]} />);
  const now = Date.now(); vi.spyOn(Date, "now").mockReturnValue(now + 240_001);
  fireEvent.click(screen.getByRole("button", { name: "Approve draft" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Expired. Not executed."));
});
