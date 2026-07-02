import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import type { PaperPosition } from "../api/types";
import { colors, radius, shadows, spacing } from "../theme";
import { formatCents, formatCurrency } from "../utils/format";
import { sideLabel } from "../utils/labels";

interface PositionCardProps {
  position: PaperPosition;
}

export function PositionCard({ position }: PositionCardProps) {
  const pnl = position.unrealized_pnl ?? 0;
  const pnlColor = pnl >= 0 ? colors.success : colors.danger;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.titleGroup}>
          <View style={styles.assetIcon}>
            <Ionicons color={colors.primary} name="analytics" size={16} />
          </View>
          <Text style={styles.title} numberOfLines={2}>
            {position.question ?? position.market_id}
          </Text>
        </View>
        <Text style={[styles.pnl, { color: pnlColor }]}>
          {formatCurrency(position.unrealized_pnl)}
        </Text>
      </View>

      <View style={styles.grid}>
        <View style={styles.metric}>
          <Text style={styles.label}>结果</Text>
          <Text style={styles.value}>
            {position.outcome_label ?? sideLabel(position.outcome_index === 0 ? "YES" : "NO")}
          </Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.label}>数量</Text>
          <Text style={styles.value}>{position.quantity}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.label}>均价</Text>
          <Text style={styles.value}>{formatCents(position.avg_price)}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.label}>标记价</Text>
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
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
    ...shadows.panel,
  },
  header: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
  },
  titleGroup: {
    alignItems: "flex-start",
    flex: 1,
    flexDirection: "row",
    gap: spacing.sm,
    minWidth: 0,
  },
  assetIcon: {
    alignItems: "center",
    backgroundColor: colors.primarySoft,
    borderColor: colors.primaryLine,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    height: 34,
    justifyContent: "center",
    width: 34,
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
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
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
