import { describe, expect, it } from "vitest";

import { buildMarketQuoteMetrics } from "../utils/marketQuote";

describe("buildMarketQuoteMetrics", () => {
  it("returns explicit bid, ask, and spread metrics for both outcomes", () => {
    const metrics = buildMarketQuoteMetrics([
      { index: 0, label: "Yes", bid: 0.54, ask: 0.56, spread: 0.02 },
      { index: 1, label: "No", bid: 0.42, ask: 0.44, spread: 0.02 },
    ]);

    expect(metrics.map((metric) => metric.label)).toEqual([
      "YES bid",
      "YES ask",
      "YES spread",
      "NO bid",
      "NO ask",
      "NO spread",
    ]);
    expect(metrics.map((metric) => metric.value)).toEqual([
      "54c",
      "56c",
      "2c",
      "42c",
      "44c",
      "2c",
    ]);
  });
});
