import { StyleSheet, Text, View } from "react-native";

import type { PaperPosition } from "../api/types";
import { colors, spacing } from "../theme";
import { formatCents, formatCurrency } from "../utils/format";

interface PositionCardProps {
  position: PaperPosition;
}

export function PositionCard({ position }: PositionCardProps) {
  const pnl = position.unrealized_pnl ?? 0;
  const pnlColor = pnl >= 0 ? colors.success : colors.danger;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title} numberOfLines={2}>
          {position.question ?? position.market_id}
        </Text>
        <Text style={[styles.pnl, { color: pnlColor }]}>
          {formatCurrency(position.unrealized_pnl)}
        </Text>
      </View>

      <View style={styles.grid}>
        <View style={styles.metric}>
          <Text style={styles.label}>Outcome</Text>
          <Text style={styles.value}>
            {position.outcome_label ?? (position.outcome_index === 0 ? "YES" : "NO")}
          </Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.label}>Qty</Text>
          <Text style={styles.value}>{position.quantity}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.label}>Avg</Text>
          <Text style={styles.value}>{formatCents(position.avg_price)}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.label}>Mark</Text>
          <Text style={styles.value}>{formatCents(position.mark_price)}</Text>
        </View>
      </View>
    </View>
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
  header: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
  },
  title: {
    color: colors.text,
    flex: 1,
    fontSize: 16,
    fontWeight: "800",
    lineHeight: 22,
  },
  pnl: {
    fontSize: 16,
    fontWeight: "800",
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metric: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    flexBasis: "48%",
    flexGrow: 1,
    gap: 3,
    padding: spacing.md,
  },
  label: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  value: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "800",
  },
});
