import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import type { RadarMarket } from "../api/types";
import { qualityTone } from "../brand";
import { colors, radius, shadows, spacing } from "../theme";
import { formatCents, formatCurrency, formatDate } from "../utils/format";
import { categoryLabel, protocolLabel } from "../utils/labels";
import { buildMarketQuoteMetrics } from "../utils/marketQuote";
import { yesProbability } from "../utils/probability";
import { RiskFlags } from "./RiskFlags";
import { SignalBadge } from "./SignalBadge";

interface MarketCardProps {
  market: RadarMarket;
  onPress?: () => void;
}

export function MarketCard({ market, onPress }: MarketCardProps) {
  const probability = yesProbability(market);
  const tone = qualityTone(market.market_quality_score);
  const scoreStyle = [
    styles.score,
    tone === "elite" && styles.scoreElite,
    tone === "solid" && styles.scoreSolid,
    tone === "watch" && styles.scoreWatch,
  ];

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.header}>
        <View style={styles.metaRow}>
          <Ionicons color={colors.textMuted} name="radio" size={13} />
          <Text style={styles.meta}>{protocolLabel(market.protocol)}</Text>
          <Text style={styles.dot}>·</Text>
          <Text style={styles.meta}>{categoryLabel(market.category)}</Text>
        </View>
        <View style={scoreStyle}>
          <Ionicons color={colors.primary} name="sparkles" size={12} />
          <Text style={styles.scoreText}>
            {market.market_quality_score ?? "-"}
          </Text>
        </View>
      </View>

      <Text style={styles.question} numberOfLines={3}>
        {market.question}
      </Text>

      <View style={styles.priceRow}>
        {buildMarketQuoteMetrics(market.outcomes).map((metric) => (
          <View key={metric.label} style={styles.priceBox}>
            <Text style={styles.priceLabel}>{metric.label}</Text>
            <Text style={styles.priceValue}>{metric.value}</Text>
          </View>
        ))}
        <View style={styles.priceBox}>
          <Text style={styles.priceLabel}>隐含概率</Text>
          <Text style={styles.priceValue}>{formatCents(probability)}</Text>
        </View>
      </View>

      <Svg height={34} viewBox="0 0 260 34" width="100%">
        <Path
          d="M2 24C34 24 35 9 64 9C96 9 92 22 124 20C157 19 152 8 188 10C220 11 225 25 258 12"
          fill="none"
          stroke={colors.primarySoft}
          strokeLinecap="round"
          strokeWidth="10"
        />
        <Path
          d="M2 24C34 24 35 9 64 9C96 9 92 22 124 20C157 19 152 8 188 10C220 11 225 25 258 12"
          fill="none"
          stroke={colors.primary}
          strokeLinecap="round"
          strokeWidth="3"
        />
      </Svg>

      <View style={styles.stats}>
        <View style={styles.statPill}>
          <Ionicons color={colors.textMuted} name="water" size={12} />
          <Text style={styles.stat}>{formatCurrency(market.liquidity_usd)}</Text>
        </View>
        <View style={styles.statPill}>
          <Ionicons color={colors.textMuted} name="pulse" size={12} />
          <Text style={styles.stat}>{formatCurrency(market.volume_usd_24h)}</Text>
        </View>
        <View style={styles.statPill}>
          <Ionicons color={colors.textMuted} name="time" size={12} />
          <Text style={styles.stat}>{formatDate(market.closes_at)}</Text>
        </View>
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
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
    ...shadows.panel,
  },
  pressed: {
    opacity: 0.78,
    transform: [{ scale: 0.99 }],
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
    fontWeight: "800",
  },
  dot: {
    color: colors.textMuted,
    fontSize: 12,
  },
  score: {
    alignItems: "center",
    backgroundColor: colors.primarySoft,
    borderColor: colors.primaryLine,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: 4,
    minHeight: 26,
    minWidth: 38,
    paddingHorizontal: 8,
  },
  scoreElite: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primaryLine,
  },
  scoreSolid: {
    backgroundColor: colors.infoSoft,
    borderColor: colors.info,
  },
  scoreWatch: {
    backgroundColor: colors.warningSoft,
    borderColor: colors.warning,
  },
  scoreText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "900",
  },
  question: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "800",
    lineHeight: 23,
  },
  priceRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  priceBox: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flexBasis: "30%",
    flexGrow: 1,
    gap: 3,
    minWidth: 88,
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
    gap: spacing.sm,
  },
  statPill: {
    alignItems: "center",
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: 5,
    minHeight: 27,
    paddingHorizontal: 9,
  },
  stat: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "800",
  },
  footer: {
    gap: spacing.sm,
  },
});
