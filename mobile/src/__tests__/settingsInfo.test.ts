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
      { label: "API 地址", value: "https://oddseye.fun" },
      { label: "雷达刷新", value: "下拉刷新；热门市场约每 2 分钟更新" },
      { label: "信号刷新", value: "策略信号约每 15 分钟重算" },
    ]);
  });
});
