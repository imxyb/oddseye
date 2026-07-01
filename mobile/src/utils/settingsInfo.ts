export interface SettingsInfoRow {
  label: string;
  value: string;
}

export function buildSettingsInfoRows(apiBaseUrl: string): SettingsInfoRow[] {
  return [
    { label: "Base URL", value: apiBaseUrl },
    {
      label: "Radar refresh",
      value: "Pull to refresh; workers update hot markets about every 5 min",
    },
    {
      label: "Signal refresh",
      value: "Workers recompute signals about every 5 min",
    },
  ];
}
