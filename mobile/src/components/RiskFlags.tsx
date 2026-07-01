import { StyleSheet, Text, View } from "react-native";

import type { RadarMarket } from "../api/types";
import { colors } from "../theme";
import { maxSpread } from "../utils/probability";

interface RiskFlagsProps {
  market?: Pick<
    RadarMarket,
    "liquidity_usd" | "closes_at" | "risk_flags" | "outcomes"
  >;
  flags?: string[];
}

function prettify(flag: string): string {
  return flag
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function deriveFlags(market?: RiskFlagsProps["market"], flags: string[] = []) {
  const derived = new Set(flags);

  market?.risk_flags?.forEach((flag) => derived.add(flag));

  if (typeof market?.liquidity_usd === "number" && market.liquidity_usd < 1000) {
    derived.add("low_liquidity");
  }

  const spread = market ? maxSpread(market) : null;
  if (typeof spread === "number" && spread > 0.08) {
    derived.add("wide_spread");
  }

  if (market?.closes_at) {
    const closesAt = new Date(market.closes_at).getTime();
    const hoursLeft = (closesAt - Date.now()) / 1000 / 60 / 60;
    if (hoursLeft > 0 && hoursLeft < 24) {
      derived.add("closing_soon");
    }
  }

  return [...derived];
}

export function RiskFlags({ market, flags = [] }: RiskFlagsProps) {
  const visibleFlags = deriveFlags(market, flags);

  if (!visibleFlags.length) {
    return null;
  }

  return (
    <View style={styles.wrap}>
      {visibleFlags.map((flag) => (
        <View key={flag} style={styles.flag}>
          <Text style={styles.flagText}>{prettify(flag)}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  flag: {
    backgroundColor: colors.warningSoft,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  flagText: {
    color: colors.warning,
    fontSize: 11,
    fontWeight: "700",
  },
});
