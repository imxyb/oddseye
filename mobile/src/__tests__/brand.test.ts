import { describe, expect, it } from "vitest";

import {
  brandAssets,
  qualityTone,
  shortCountLabel,
} from "../brand";

describe("brand presentation helpers", () => {
  it("exposes the app icon assets used by Expo and native iOS", () => {
    expect(brandAssets.logoSvg).toBe("assets/oddseye-logo.svg");
    expect(brandAssets.expoIcon).toBe("assets/icon.png");
    expect(brandAssets.adaptiveIcon).toBe("assets/adaptive-icon.png");
    expect(brandAssets.iosIcon).toContain("App-Icon-1024x1024@1x.png");
  });

  it("maps market quality scores to compact visual tones", () => {
    expect(qualityTone(91)).toBe("elite");
    expect(qualityTone(78)).toBe("solid");
    expect(qualityTone(55)).toBe("watch");
    expect(qualityTone(null)).toBe("muted");
  });

  it("formats large counts for command deck summary widgets", () => {
    expect(shortCountLabel(42)).toBe("42");
    expect(shortCountLabel(1_240)).toBe("1.2k");
    expect(shortCountLabel(98_100)).toBe("98k");
  });
});
