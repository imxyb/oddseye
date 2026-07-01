import type { Freshness } from "../api/types";

export interface FreshnessNotice {
  title: string;
  detail: string;
}

function formatAge(ageSeconds?: number | null): string {
  if (ageSeconds === undefined || ageSeconds === null) {
    return "unknown";
  }

  if (ageSeconds < 60) {
    return "<1 min";
  }

  const minutes = Math.round(ageSeconds / 60);
  if (minutes < 60) {
    return `${minutes} min`;
  }

  const hours = Math.round(minutes / 60);
  return `${hours} hr`;
}

export function buildFreshnessNotice(freshness?: Freshness | null): FreshnessNotice | null {
  if (!freshness?.is_stale) {
    return null;
  }

  return {
    title: "Cached price",
    detail: `Last updated ${formatAge(freshness.age_seconds)} ago. Refresh before opening a paper position.`,
  };
}
