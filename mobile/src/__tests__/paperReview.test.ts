import { describe, expect, it } from "vitest";

import {
  buildReviewRollupSections,
  buildTradeTraceRows,
} from "../utils/paperReview";

const review = {
  strategy_stats: [
    {
      key: "crypto_threshold_v2",
      total_trades: 4,
      total_notional: 220,
      average_edge: 0.1,
      realized_pnl: 8,
      win_rate: 0.5,
      max_drawdown: 5,
    },
  ],
  category_stats: [
    {
      key: "crypto",
      total_trades: 4,
      total_notional: 220,
      average_edge: 0.1,
      realized_pnl: 8,
      win_rate: 0.5,
      max_drawdown: 5,
    },
  ],
  trades: [
    {
      fill_id: "fill-1",
      order_id: "order-1",
      signal_id: "signal-1",
      snapshot_id: 42,
      market_id: "market-1",
      question: "Will BTC be above $80,000?",
      category: "crypto",
      strategy_code: "crypto_threshold_v2",
      side: "BUY",
      outcome_index: 0,
      price: 0.55,
      quantity: 10,
      notional: 5.5,
      fee: 0.01,
      edge: 0.1,
      market_quality_score: 80,
      created_at: "2026-07-02T00:00:00Z",
    },
  ],
};

describe("paper review presentation", () => {
  it("formats strategy and category review rollups", () => {
    const sections = buildReviewRollupSections(review);

    expect(sections.map((section) => section.title)).toEqual([
      "策略复盘",
      "分类复盘",
    ]);
    expect(sections[0]?.items[0]?.metrics).toEqual([
      { label: "交易", value: "4" },
      { label: "盈亏", value: "$8.00" },
      { label: "胜率", value: "50%" },
      { label: "优势", value: "10%" },
      { label: "回撤", value: "$5.00" },
    ]);
  });

  it("formats trade rows with signal, snapshot, and price traceability", () => {
    const rows = buildTradeTraceRows(review.trades);

    expect(rows[0]).toMatchObject({
      id: "fill-1",
      title: "Will BTC be above $80,000?",
      price: "55c",
      signal: "signal-1",
      snapshot: "42",
      strategy: "crypto_threshold_v2",
    });
  });
});
