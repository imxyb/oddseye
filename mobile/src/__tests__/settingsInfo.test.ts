import { describe, expect, it } from "vitest";

import { buildSettingsInfoRows } from "../utils/settingsInfo";

describe("buildSettingsInfoRows", () => {
  it("includes API base URL and refresh cadence rows", () => {
    const rows = buildSettingsInfoRows("https://oddseye.fun", {
      jobs: {
        hot_market_snapshot_seconds: 120,
        signal_seconds: 900,
      },
    });

    expect(rows).toEqual([
      { label: "Base URL", value: "https://oddseye.fun" },
      { label: "Radar refresh", value: "Pull to refresh; workers update hot markets about every 2 min" },
      { label: "Signal refresh", value: "Workers recompute signals about every 15 min" },
    ]);
  });
});
