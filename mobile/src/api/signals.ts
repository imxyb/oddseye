import { apiFetch } from "./client";
import { toQueryString } from "./queryString";
import type {
  MarketCategory,
  PaperOrder,
  SignalPaperOrderRequest,
  SignalsResponse,
} from "./types";

export interface SignalsParams {
  action?: string;
  category?: MarketCategory;
  minEdge?: number;
  limit?: number;
}

export const signalKeys = {
  list: (params: SignalsParams) => ["signals", params] as const,
};

export function getSignals(params: SignalsParams = {}) {
  return apiFetch<SignalsResponse>(`/signals${toQueryString(params)}`);
}

export function createPaperOrderFromSignal(
  signalId: string,
  input: SignalPaperOrderRequest,
) {
  return apiFetch<PaperOrder>(
    `/signals/${encodeURIComponent(signalId)}/paper-order`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}
