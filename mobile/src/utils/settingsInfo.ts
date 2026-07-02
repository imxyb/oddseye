import type { SettingsUsage } from "../api/types";

export interface SettingsInfoRow {
  label: string;
  value: string;
}

export function buildSettingsInfoRows(
  apiBaseUrl: string,
  settingsUsage?: Pick<SettingsUsage, "jobs"> | null,
): SettingsInfoRow[] {
  const hotMarketCadence = formatCadence(
    settingsUsage?.jobs?.hot_market_snapshot_seconds,
    "5 min",
  );
  const signalCadence = formatCadence(
    settingsUsage?.jobs?.signal_seconds,
    "5 min",
  );

  return [
    { label: "API 地址", value: apiBaseUrl },
    {
      label: "雷达刷新",
      value: `下拉刷新；热门市场约每 ${hotMarketCadence}更新`,
    },
    {
      label: "信号刷新",
      value: `策略信号约每 ${signalCadence}重算`,
    },
  ];
}

function formatCadence(seconds: number | undefined, fallback: string): string {
  if (!seconds || seconds <= 0) {
    return fallback;
  }
  if (seconds % 3600 === 0) {
    return `${seconds / 3600} 小时`;
  }
  if (seconds % 60 === 0) {
    return `${seconds / 60} 分钟`;
  }
  return `${seconds} 秒`;
}
