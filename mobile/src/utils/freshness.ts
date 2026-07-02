import type { Freshness } from "../api/types";

export interface FreshnessNotice {
  title: string;
  detail: string;
}

function formatAge(ageSeconds?: number | null): string {
  if (ageSeconds === undefined || ageSeconds === null) {
    return "未知";
  }

  if (ageSeconds < 60) {
    return "不到 1 分钟";
  }

  const minutes = Math.round(ageSeconds / 60);
  if (minutes < 60) {
    return `${minutes} 分钟`;
  }

  const hours = Math.round(minutes / 60);
  return `${hours} 小时`;
}

export function buildFreshnessNotice(freshness?: Freshness | null): FreshnessNotice | null {
  if (!freshness?.is_stale) {
    return null;
  }

  return {
    title: "价格可能滞后",
    detail: `上次更新约 ${formatAge(freshness.age_seconds)}前。建仓前建议刷新。`,
  };
}
