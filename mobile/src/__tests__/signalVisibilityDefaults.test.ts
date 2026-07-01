import { describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();

vi.mock("../api/client", () => ({
  apiFetch,
}));

describe("signal visibility defaults", () => {
  it("requests all signals by default while preserving caller limits", async () => {
    apiFetch.mockResolvedValue({ items: [] });

    const { getSignals } = await import("../api/signals");

    await getSignals({ limit: 50 });

    expect(apiFetch).toHaveBeenCalledWith("/signals?limit=50");
  });

  it("passes an action filter only when selected", async () => {
    apiFetch.mockResolvedValue({ items: [] });

    const { getSignals } = await import("../api/signals");

    await getSignals({ action: "BUY", limit: 50 });

    expect(apiFetch).toHaveBeenCalledWith("/signals?action=BUY&limit=50");
  });

  it("sorts radar by signal edge by default", async () => {
    const { useFilterStore } = await import("../stores/filterStore");

    expect(useFilterStore.getState().sort).toBe("edge");
  });
});
