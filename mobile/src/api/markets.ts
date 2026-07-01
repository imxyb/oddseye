import { apiFetch } from "./client";
import { toQueryString } from "./queryString";
import type {
  MarketBarsResponse,
  MarketDetail,
  MarketRefreshResponse,
} from "./types";

export interface MarketBarsParams {
  range?: "24h" | "7d" | "30d" | "all";
  resolution?: "min15" | "hour1" | "hour4" | "day1";
}

export const marketKeys = {
  detail: (marketId: string) => ["markets", marketId] as const,
  bars: (marketId: string, params: MarketBarsParams) =>
    ["markets", marketId, "bars", params] as const,
};

export function getMarket(marketId: string) {
  return apiFetch<MarketDetail>(`/markets/${encodeURIComponent(marketId)}`);
}

export function getMarketBars(
  marketId: string,
  params: MarketBarsParams = { range: "7d", resolution: "hour1" },
) {
  return apiFetch<MarketBarsResponse>(
    `/markets/${encodeURIComponent(marketId)}/bars${toQueryString(params)}`,
  );
}

export function refreshMarket(marketId: string) {
  return apiFetch<MarketRefreshResponse>(
    `/markets/${encodeURIComponent(marketId)}/refresh`,
    {
      method: "POST",
    },
  );
}
