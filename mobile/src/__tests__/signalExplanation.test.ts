import { describe, expect, it } from "vitest";

import { buildSignalExplanationRows } from "../utils/signalExplanation";

describe("buildSignalExplanationRows", () => {
  it("shows backend reason codes and risk flags as signal rationale", () => {
    const rows = buildSignalExplanationRows({
      reason_codes: ["MODEL_EDGE_POSITIVE", "BUY_YES_EDGE"],
      risk_flags: ["QUALITY_BELOW_GATE"],
    });

    expect(rows).toEqual([
      { label: "依据", value: "模型优势为正 · YES 结果有优势" },
      { label: "风险", value: "质量偏低" },
    ]);
  });
});
