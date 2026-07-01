import { beforeEach, describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();

vi.mock("../api/client", () => ({
  apiFetch,
}));

describe("settings API", () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  it("loads usage and runtime settings", async () => {
    apiFetch.mockResolvedValueOnce({ provider: "codex" });

    const { getSettingsUsage } = await import("../api/settings");
    await getSettingsUsage();

    expect(apiFetch).toHaveBeenCalledWith("/settings/usage");
  });
});
