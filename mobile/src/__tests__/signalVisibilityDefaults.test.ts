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

  it("requests edgeful opportunities for the default signals screen filter", async () => {
    apiFetch.mockResolvedValue({ items: [] });

    const { getSignals } = await import("../api/signals");
    const { defaultSignalFilterKey, signalFilterParams } = await import(
      "../utils/signalVisibility"
    );

    await getSignals({ ...signalFilterParams(defaultSignalFilterKey), limit: 50 });

    expect(apiFetch).toHaveBeenCalledWith("/signals?minEdge=0.07&limit=50");
  });

  it("does not apply the edge default when viewing ignored signals explicitly", async () => {
    const { signalFilterParams } = await import("../utils/signalVisibility");

    expect(signalFilterParams("IGNORE")).toEqual({ action: "IGNORE" });
  });

  it("exposes V2 blocked and reduce signals as explicit filters", async () => {
    const { signalFilterParams, signalFilters } = await import("../utils/signalVisibility");

    expect(signalFilters.map((filter) => filter.key)).toContain("BLOCKED");
    expect(signalFilters.map((filter) => filter.key)).toContain("REDUCE");
    expect(signalFilterParams("BLOCKED")).toEqual({ action: "BLOCKED" });
    expect(signalFilterParams("REDUCE")).toEqual({ action: "REDUCE" });
  });

  it("only treats executable BUY signals as orderable", async () => {
    const { isOrderableSignal } = await import("../utils/signalVisibility");

    expect(
      isOrderableSignal({
        action: "BUY",
        side: "NO",
        executable_price: 0.5,
      }),
    ).toBe(true);
    expect(
      isOrderableSignal({
        action: "IGNORE",
        executable_price: null,
      }),
    ).toBe(false);
    expect(
      isOrderableSignal({
        action: "HOLD",
        side: "NO",
        executable_price: 0.4,
      }),
    ).toBe(false);
  });

  it("sorts radar by signal edge by default", async () => {
    const { useFilterStore } = await import("../stores/filterStore");

    expect(useFilterStore.getState().sort).toBe("edge");
  });
});
