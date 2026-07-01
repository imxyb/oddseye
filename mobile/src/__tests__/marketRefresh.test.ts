import { describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();

vi.mock("../api/client", () => ({
  apiFetch,
}));

describe("market refresh API", () => {
  it("posts to the current market refresh endpoint", async () => {
    apiFetch.mockResolvedValue({
      market_id: "market-1",
      records_processed: 1,
      market: {},
    });

    const { refreshMarket } = await import("../api/markets");

    await refreshMarket("market-1");

    expect(apiFetch).toHaveBeenCalledWith("/markets/market-1/refresh", {
      method: "POST",
    });
  });
});
