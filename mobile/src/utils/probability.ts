import type { MarketBar, MarketOutcome, RadarMarket } from "../api/types";

export function midpoint(outcome?: MarketOutcome): number | null {
  if (!outcome) {
    return null;
  }

  if (typeof outcome.bid === "number" && typeof outcome.ask === "number") {
    return (outcome.bid + outcome.ask) / 2;
  }

  return outcome.ask ?? outcome.bid ?? null;
}

export function yesProbability(market: Pick<RadarMarket, "outcomes">): number | null {
  return midpoint(market.outcomes.find((outcome) => outcome.index === 0));
}

export function maxSpread(market: Pick<RadarMarket, "outcomes">): number | null {
  const spreads = market.outcomes
    .map((outcome) => outcome.spread)
    .filter((spread): spread is number => typeof spread === "number");

  return spreads.length ? Math.max(...spreads) : null;
}

export function chartRange(bars: MarketBar[]): [number, number] {
  const values = bars.flatMap((bar) => [
    bar.yes.c,
    bar.no?.c,
  ]).filter((value): value is number => typeof value === "number");

  if (!values.length) {
    return [0, 1];
  }

  const min = Math.max(0, Math.min(...values) - 0.05);
  const max = Math.min(1, Math.max(...values) + 0.05);
  return min === max ? [Math.max(0, min - 0.1), Math.min(1, max + 0.1)] : [min, max];
}
