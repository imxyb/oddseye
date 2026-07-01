import { describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();

vi.mock("../api/client", () => ({
  apiFetch,
}));

describe("market bars API", () => {
  it("returns typed freshness and source metadata", async () => {
    apiFetch.mockResolvedValue({
      market_id: "market-1",
      source: "local_snapshots",
      bars: [],
      freshness: {
        is_stale: false,
        codex_usage_hint: {
          today_requests: 1,
          month_requests: 1,
          fetch_profile: "light",
        },
      },
    });

    const { getMarketBars } = await import("../api/markets");

    const response = await getMarketBars("market-1");

    expect(response.source).toBe("local_snapshots");
    expect(response.freshness?.codex_usage_hint?.fetch_profile).toBe("light");
  });
});
