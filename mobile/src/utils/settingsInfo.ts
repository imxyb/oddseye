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
    { label: "Base URL", value: apiBaseUrl },
    {
      label: "Radar refresh",
      value: `Pull to refresh; workers update hot markets about every ${hotMarketCadence}`,
    },
    {
      label: "Signal refresh",
      value: `Workers recompute signals about every ${signalCadence}`,
    },
  ];
}

function formatCadence(seconds: number | undefined, fallback: string): string {
  if (!seconds || seconds <= 0) {
    return fallback;
  }
  if (seconds % 3600 === 0) {
    return `${seconds / 3600} hr`;
  }
  if (seconds % 60 === 0) {
    return `${seconds / 60} min`;
  }
  return `${seconds} sec`;
}
