import { apiFetch } from "./client";
import type { SettingsUsage } from "./types";

export const settingsKeys = {
  usage: ["settings", "usage"] as const,
};

export function getSettingsUsage() {
  return apiFetch<SettingsUsage>("/settings/usage");
}
