import { describe, expect, it } from "vitest";

import { buildFreshnessNotice } from "../utils/freshness";

describe("buildFreshnessNotice", () => {
  it("returns a visible warning for stale market prices", () => {
    expect(
      buildFreshnessNotice({
        age_seconds: 1_201,
        codex_usage_hint: {
          fetch_profile: "light",
          month_requests: 2_400,
          today_requests: 80,
        },
        is_stale: true,
        last_snapshot_at: "2026-07-02T00:00:00+08:00",
      }),
    ).toEqual({
      title: "Cached price",
      detail: "Last updated 20 min ago. Refresh before opening a paper position.",
    });
  });

  it("does not show a warning for fresh market prices", () => {
    expect(
      buildFreshnessNotice({
        age_seconds: 90,
        codex_usage_hint: {
          fetch_profile: "light",
          month_requests: 2_400,
          today_requests: 80,
        },
        is_stale: false,
        last_snapshot_at: "2026-07-02T00:00:00+08:00",
      }),
    ).toBeNull();
  });
});
