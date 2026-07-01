import { Pressable, StyleSheet, Text, View } from "react-native";

import type { RadarMarket } from "../api/types";
import { colors, spacing } from "../theme";
import { formatCents, formatCurrency, formatDate } from "../utils/format";
import { midpoint, yesProbability } from "../utils/probability";
import { RiskFlags } from "./RiskFlags";
import { SignalBadge } from "./SignalBadge";

interface MarketCardProps {
  market: RadarMarket;
  onPress?: () => void;
}

export function MarketCard({ market, onPress }: MarketCardProps) {
  const yes = market.outcomes.find((outcome) => outcome.index === 0);
  const no = market.outcomes.find((outcome) => outcome.index === 1);
  const probability = yesProbability(market);

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.header}>
        <View style={styles.metaRow}>
          <Text style={styles.meta}>{market.protocol}</Text>
          <Text style={styles.dot}>/</Text>
          <Text style={styles.meta}>{market.category}</Text>
        </View>
        <View style={styles.score}>
          <Text style={styles.scoreText}>
            {market.market_quality_score ?? "-"}
          </Text>
        </View>
      </View>

      <Text style={styles.question} numberOfLines={3}>
        {market.question}
      </Text>

      <View style={styles.priceRow}>
        <View style={styles.priceBox}>
          <Text style={styles.priceLabel}>YES</Text>
          <Text style={styles.priceValue}>{formatCents(midpoint(yes))}</Text>
        </View>
        <View style={styles.priceBox}>
          <Text style={styles.priceLabel}>NO</Text>
          <Text style={styles.priceValue}>{formatCents(midpoint(no))}</Text>
        </View>
        <View style={styles.priceBox}>
          <Text style={styles.priceLabel}>IMPLIED</Text>
          <Text style={styles.priceValue}>{formatCents(probability)}</Text>
        </View>
      </View>

      <View style={styles.stats}>
        <Text style={styles.stat}>Liq {formatCurrency(market.liquidity_usd)}</Text>
        <Text style={styles.stat}>Vol {formatCurrency(market.volume_usd_24h)}</Text>
        <Text style={styles.stat}>Close {formatDate(market.closes_at)}</Text>
      </View>

      <View style={styles.footer}>
        <SignalBadge
          action={market.latest_signal?.action}
          side={market.latest_signal?.side}
          compact
        />
        <RiskFlags market={market} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
  },
  pressed: {
    opacity: 0.72,
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  metaRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: 6,
  },
  meta: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  dot: {
    color: colors.textMuted,
    fontSize: 12,
  },
  score: {
    alignItems: "center",
    backgroundColor: colors.primarySoft,
    borderRadius: 6,
    minWidth: 38,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  scoreText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
  },
  question: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
    lineHeight: 23,
  },
  priceRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  priceBox: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    flex: 1,
    gap: 3,
    padding: spacing.md,
  },
  priceLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  priceValue: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "800",
  },
  stats: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  stat: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  footer: {
    gap: spacing.sm,
  },
});
