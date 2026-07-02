import type {
  PaperReviewResponse,
  PaperReviewRollup,
  PaperReviewTrade,
} from "../api/types";
import { formatCents, formatCurrency, formatDate, formatPercent } from "./format";

export interface ReviewMetric {
  label: string;
  value: string;
}

export interface ReviewRollupItem {
  key: string;
  metrics: ReviewMetric[];
}

export interface ReviewRollupSection {
  title: string;
  items: ReviewRollupItem[];
}

export interface TradeTraceRow {
  id: string;
  title: string;
  subtitle: string;
  price: string;
  signal: string;
  snapshot: string;
  strategy: string;
  timestamp: string;
}

export function buildReviewRollupSections(
  review: PaperReviewResponse,
): ReviewRollupSection[] {
  return [
    {
      title: "Strategy review",
      items: review.strategy_stats.map(buildRollupItem),
    },
    {
      title: "Category review",
      items: review.category_stats.map(buildRollupItem),
    },
  ];
}

export function buildTradeTraceRows(trades: PaperReviewTrade[]): TradeTraceRow[] {
  return trades.slice(0, 8).map((trade) => ({
    id: trade.fill_id,
    title: trade.question,
    subtitle: [trade.side, trade.category, `Qty ${formatQuantity(trade.quantity)}`]
      .filter(Boolean)
      .join(" · "),
    price: formatCents(trade.price),
    signal: trade.signal_id ?? "-",
    snapshot: trade.snapshot_id === null || trade.snapshot_id === undefined
      ? "-"
      : String(trade.snapshot_id),
    strategy: trade.strategy_code ?? "manual",
    timestamp: formatDate(trade.created_at),
  }));
}

function buildRollupItem(rollup: PaperReviewRollup): ReviewRollupItem {
  return {
    key: rollup.key,
    metrics: [
      { label: "Trades", value: String(rollup.total_trades) },
      { label: "PnL", value: formatCurrency(rollup.realized_pnl) },
      { label: "Win", value: formatPercent(rollup.win_rate) },
      { label: "Edge", value: formatPercent(rollup.average_edge) },
      { label: "Drawdown", value: formatCurrency(rollup.max_drawdown) },
    ],
  };
}

function formatQuantity(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
  }).format(value);
}
