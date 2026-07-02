import { describe, expect, it } from "vitest";

import {
  actionLabel,
  categoryLabel,
  qualityComponentLabel,
  riskCodeLabel,
  sideLabel,
} from "../utils/labels";

describe("presentation labels", () => {
  it("localizes high-frequency trading labels", () => {
    expect(actionLabel("BUY")).toBe("买入");
    expect(actionLabel("OBSERVE")).toBe("观察");
    expect(actionLabel(null)).toBe("无信号");
    expect(sideLabel("YES")).toBe("YES 结果");
    expect(categoryLabel("economics")).toBe("宏观");
  });

  it("localizes known risk and quality codes while keeping unknown codes readable", () => {
    expect(riskCodeLabel("LOW_LIQUIDITY")).toBe("低流动性");
    expect(riskCodeLabel("QUALITY_BELOW_GATE")).toBe("质量偏低");
    expect(riskCodeLabel("CUSTOM_BACKEND_CODE")).toBe("CUSTOM BACKEND CODE");
    expect(qualityComponentLabel("resolution_clarity")).toBe("结算清晰度");
  });
});
