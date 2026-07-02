export const brandAssets = {
  logoSvg: "assets/oddseye-logo.svg",
  expoIcon: "assets/icon.png",
  adaptiveIcon: "assets/adaptive-icon.png",
  iosIcon:
    "ios/OddsEye/Images.xcassets/AppIcon.appiconset/App-Icon-1024x1024@1x.png",
} as const;

export type QualityTone = "elite" | "solid" | "watch" | "muted";

export function qualityTone(score?: number | null): QualityTone {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "muted";
  }

  if (score >= 85) {
    return "elite";
  }

  if (score >= 70) {
    return "solid";
  }

  return "watch";
}

export function shortCountLabel(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  if (Math.abs(value) >= 10_000) {
    return `${Math.round(value / 1_000)}k`;
  }

  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(1).replace(/\.0$/, "")}k`;
  }

  return String(Math.round(value));
}
