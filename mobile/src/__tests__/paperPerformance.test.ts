import { describe, expect, it } from "vitest";

import { buildPerformanceMetrics } from "../utils/paperPerformance";

describe("buildPerformanceMetrics", () => {
  it("includes cash, PnL, win rate, drawdown, and trade count", () => {
    const metrics = buildPerformanceMetrics({
      equity: 10050,
      cash: 9500,
      unrealized_pnl: 25,
      realized_pnl: 75,
      win_rate: 0.5,
      max_drawdown: 0.081,
      total_trades: 4,
    });

    expect(metrics.map((metric) => metric.label)).toEqual([
      "Equity",
      "Cash",
      "Unrealized",
      "Realized",
      "Total PnL",
      "Win rate",
      "Drawdown",
      "Trades",
    ]);
    expect(metrics.map((metric) => metric.value)).toContain("$100.00");
    expect(metrics.map((metric) => metric.value)).toContain("8%");
    expect(metrics.map((metric) => metric.value)).toContain("4");
  });
});
