import type { MarketOutcome } from "../api/types";
import { formatCents } from "./format";
import { sideLabel } from "./labels";

export interface MarketQuoteMetric {
  label: string;
  value: string;
}

export function buildMarketQuoteMetrics(outcomes: MarketOutcome[]): MarketQuoteMetric[] {
  return outcomes
    .slice()
    .sort((left, right) => left.index - right.index)
    .flatMap((outcome) => {
      const label = sideLabel(outcome.label.toUpperCase()) || outcome.label.toUpperCase();
      return [
        { label: `${label} 买价`, value: formatCents(outcome.bid) },
        { label: `${label} 卖价`, value: formatCents(outcome.ask) },
        { label: `${label} 价差`, value: formatCents(outcome.spread) },
      ];
    });
}
