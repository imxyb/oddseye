import { apiFetch } from "./client";
import { toQueryString } from "./queryString";
import type {
  MarketCategory,
  Protocol,
  RadarMarketsResponse,
} from "./types";

export interface RadarMarketsParams {
  category?: MarketCategory;
  protocol?: Protocol;
  q?: string;
  sort?: "quality" | "volume" | "liquidity" | "closingSoon" | "edge";
  minQuality?: number;
  minVolume?: number;
  minLiquidity?: number;
  maxSpread?: number;
  closesWithinHours?: number;
  limit?: number;
  offset?: number;
}

export const radarKeys = {
  markets: (params: RadarMarketsParams) => ["radar", "markets", params] as const,
};

export function getRadarMarkets(params: RadarMarketsParams = {}) {
  return apiFetch<RadarMarketsResponse>(
    `/radar/markets${toQueryString(params)}`,
  );
}
