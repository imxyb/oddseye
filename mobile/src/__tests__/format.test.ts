import { describe, expect, it } from "vitest";

import { formatDate } from "../utils/format";

describe("formatDate", () => {
  it("uses compact Chinese date labels for UI timestamps", () => {
    expect(formatDate("2026-07-02T08:05:00+08:00")).toBe("7月2日 08:05");
  });
});
