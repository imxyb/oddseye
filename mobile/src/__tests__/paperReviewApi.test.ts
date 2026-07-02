import { beforeEach, describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();

vi.mock("../api/client", () => ({
  apiFetch,
}));

describe("paper review API", () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  it("loads paper review rollups and trade traceability rows", async () => {
    apiFetch.mockResolvedValueOnce({ strategy_stats: [], category_stats: [], trades: [] });

    const { getPaperReview } = await import("../api/paper");
    await getPaperReview();

    expect(apiFetch).toHaveBeenCalledWith("/paper/review");
  });
});
