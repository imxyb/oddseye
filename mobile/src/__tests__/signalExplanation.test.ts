import { describe, expect, it } from "vitest";

import { buildSignalExplanationRows } from "../utils/signalExplanation";

describe("buildSignalExplanationRows", () => {
  it("shows backend reason codes and risk flags as signal rationale", () => {
    const rows = buildSignalExplanationRows({
      reason_codes: ["MODEL_EDGE_POSITIVE", "BUY_YES_EDGE"],
      risk_flags: ["QUALITY_BELOW_GATE"],
    });

    expect(rows).toEqual([
      { label: "Reason", value: "MODEL_EDGE_POSITIVE, BUY_YES_EDGE" },
      { label: "Risk", value: "QUALITY_BELOW_GATE" },
    ]);
  });
});
