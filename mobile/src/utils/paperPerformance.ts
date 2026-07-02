import type { PaperPerformance } from "../api/types";
import { formatCurrency, formatPercent } from "./format";

export interface PerformanceMetric {
  label: string;
  value: string;
}

export function buildPerformanceMetrics(performance: PaperPerformance): PerformanceMetric[] {
  const totalPnl = performance.realized_pnl + performance.unrealized_pnl;

  return [
    { label: "权益", value: formatCurrency(performance.equity) },
    { label: "现金", value: formatCurrency(performance.cash) },
    { label: "浮盈", value: formatCurrency(performance.unrealized_pnl) },
    { label: "已实现", value: formatCurrency(performance.realized_pnl) },
    { label: "总盈亏", value: formatCurrency(totalPnl) },
    { label: "胜率", value: formatPercent(performance.win_rate) },
    { label: "回撤", value: formatPercent(performance.max_drawdown) },
    { label: "交易", value: String(performance.total_trades) },
  ];
}
