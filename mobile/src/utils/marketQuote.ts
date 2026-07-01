import type { MarketOutcome } from "../api/types";
import { formatCents } from "./format";

export interface MarketQuoteMetric {
  label: string;
  value: string;
}

export function buildMarketQuoteMetrics(outcomes: MarketOutcome[]): MarketQuoteMetric[] {
  return outcomes
    .slice()
    .sort((left, right) => left.index - right.index)
    .flatMap((outcome) => {
      const label = outcome.label.toUpperCase();
      return [
        { label: `${label} bid`, value: formatCents(outcome.bid) },
        { label: `${label} ask`, value: formatCents(outcome.ask) },
        { label: `${label} spread`, value: formatCents(outcome.spread) },
      ];
    });
}
