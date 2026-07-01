import { create } from "zustand";

import type { MarketCategory, Protocol } from "../api/types";
import type { RadarMarketsParams } from "../api/radar";

interface FilterState {
  category: MarketCategory;
  protocol: Protocol | undefined;
  sort: NonNullable<RadarMarketsParams["sort"]>;
  minQuality: number;
  minVolume: number;
  minLiquidity: number;
  maxSpread: number;
  closesWithinHours: number | undefined;
  q: string;
  setCategory: (category: MarketCategory) => void;
  setProtocol: (protocol: Protocol | undefined) => void;
  setSort: (sort: NonNullable<RadarMarketsParams["sort"]>) => void;
  setMinQuality: (minQuality: number) => void;
  setMinVolume: (minVolume: number) => void;
  setMinLiquidity: (minLiquidity: number) => void;
  setMaxSpread: (maxSpread: number) => void;
  setClosesWithinHours: (closesWithinHours: number | undefined) => void;
  setQuery: (q: string) => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  category: "crypto",
  protocol: undefined,
  sort: "edge",
  minQuality: 65,
  minVolume: 500,
  minLiquidity: 1000,
  maxSpread: 0.08,
  closesWithinHours: undefined,
  q: "",
  setCategory: (category) => set({ category }),
  setProtocol: (protocol) => set({ protocol }),
  setSort: (sort) => set({ sort }),
  setMinQuality: (minQuality) => set({ minQuality }),
  setMinVolume: (minVolume) => set({ minVolume }),
  setMinLiquidity: (minLiquidity) => set({ minLiquidity }),
  setMaxSpread: (maxSpread) => set({ maxSpread }),
  setClosesWithinHours: (closesWithinHours) => set({ closesWithinHours }),
  setQuery: (q) => set({ q }),
}));
