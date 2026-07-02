import { describe, expect, it } from "vitest";

import { radarCategories } from "../utils/radarFilters";

describe("radar filters", () => {
  it("matches the documented Crypto, Macro, and Watchlist tabs", () => {
    expect(radarCategories).toEqual(["crypto", "economics", "watchlist"]);
  });
});
