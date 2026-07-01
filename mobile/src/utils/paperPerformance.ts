import type { PaperPerformance } from "../api/types";
import { formatCurrency, formatPercent } from "./format";

export interface PerformanceMetric {
  label: string;
  value: string;
}

export function buildPerformanceMetrics(performance: PaperPerformance): PerformanceMetric[] {
  const totalPnl = performance.realized_pnl + performance.unrealized_pnl;

  return [
    { label: "Equity", value: formatCurrency(performance.equity) },
    { label: "Cash", value: formatCurrency(performance.cash) },
    { label: "Unrealized", value: formatCurrency(performance.unrealized_pnl) },
    { label: "Realized", value: formatCurrency(performance.realized_pnl) },
    { label: "Total PnL", value: formatCurrency(totalPnl) },
    { label: "Win rate", value: formatPercent(performance.win_rate) },
    { label: "Drawdown", value: formatPercent(performance.max_drawdown) },
    { label: "Trades", value: String(performance.total_trades) },
  ];
}
