import { apiFetch } from "./client";
import type {
  PaperOrder,
  PaperOrderRequest,
  PaperPerformance,
  PaperPositionsResponse,
  PaperReviewResponse,
} from "./types";

export const paperKeys = {
  positions: ["paper", "positions"] as const,
  performance: ["paper", "performance"] as const,
  review: ["paper", "review"] as const,
};

export function createPaperOrder(input: PaperOrderRequest) {
  return apiFetch<PaperOrder>("/paper/orders", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getPaperPositions() {
  return apiFetch<PaperPositionsResponse>("/paper/positions");
}

export function getPaperPerformance() {
  return apiFetch<PaperPerformance>("/paper/performance");
}

export function getPaperReview() {
  return apiFetch<PaperReviewResponse>("/paper/review");
}
