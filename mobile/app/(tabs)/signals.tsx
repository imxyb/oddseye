import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { getSignals, signalKeys } from "../../src/api/signals";
import type { Signal } from "../../src/api/types";
import { shortCountLabel } from "../../src/brand";
import { SignalBadge } from "../../src/components/SignalBadge";
import { colors, radius, shadows, spacing } from "../../src/theme";
import { formatCents, formatPercent } from "../../src/utils/format";
import { categoryLabel } from "../../src/utils/labels";
import { buildSignalExplanationRows } from "../../src/utils/signalExplanation";
import {
  defaultSignalFilterKey,
  isOrderableSignal,
  signalFilterParams,
  signalFilters,
  type SignalFilterKey,
} from "../../src/utils/signalVisibility";

function ActionFilter({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.filterButton, selected && styles.filterActive]}
    >
      <Text style={[styles.filterText, selected && styles.filterTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  const explanationRows = buildSignalExplanationRows(signal);

  return (
    <Pressable
      accessibilityRole="button"
      onPress={() =>
        router.push({
          pathname: "/market/[id]",
          params: { id: signal.market_id },
        })
      }
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.cardHeader}>
        <SignalBadge action={signal.action} side={signal.side} />
        <Text style={styles.category}>{categoryLabel(signal.category)}</Text>
      </View>

      <Text style={styles.question} numberOfLines={3}>
        {signal.question}
      </Text>

      <View style={styles.metrics}>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>优势</Text>
          <Text style={styles.metricValue}>{formatPercent(signal.edge)}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>置信</Text>
          <Text style={styles.metricValue}>
            {formatPercent(signal.confidence)}
          </Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>限价</Text>
          <Text style={styles.metricValue}>
            {formatCents(signal.executable_price)}
          </Text>
        </View>
      </View>

      {signal.rationale ? (
        <Text style={styles.rationale} numberOfLines={2}>
          {signal.rationale}
        </Text>
      ) : null}

      {explanationRows.length > 0 ? (
        <View style={styles.explanations}>
          {explanationRows.map((row) => (
            <View key={row.label} style={styles.explanationRow}>
              <Text style={styles.explanationLabel}>{row.label}</Text>
              <Text style={styles.explanationValue} numberOfLines={1}>
                {row.value}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      {isOrderableSignal(signal) ? (
        <Pressable
          accessibilityRole="button"
          onPress={() =>
            router.push({
              pathname: "/paper/new-order",
              params: {
                signalId: signal.signal_id,
                limitPrice: String(signal.executable_price),
              },
            })
          }
          style={styles.orderButton}
        >
          <Ionicons color={colors.background} name="paper-plane" size={15} />
          <Text style={styles.orderText}>纸上下单</Text>
        </Pressable>
      ) : null}
    </Pressable>
  );
}

export default function SignalsScreen() {
  const [selectedFilter, setSelectedFilter] = useState<SignalFilterKey>(
    defaultSignalFilterKey,
  );
  const params = useMemo(
    () => ({
      ...signalFilterParams(selectedFilter),
      limit: 50,
    }),
    [selectedFilter],
  );
  const signalsQuery = useQuery({
    queryKey: signalKeys.list(params),
    queryFn: () => getSignals(params),
  });
  const signals = signalsQuery.data?.items ?? [];

  return (
    <SafeAreaView edges={["left", "right"]} style={styles.safeArea}>
      <FlatList
        contentContainerStyle={styles.listContent}
        data={signals}
        keyExtractor={(item) => item.signal_id}
        ListHeaderComponent={
          <View style={styles.header}>
            <View style={styles.hero}>
              <View>
                <Text style={styles.kicker}>Signal stream</Text>
                <Text style={styles.heroValue}>
                  {signalsQuery.isLoading ? "..." : shortCountLabel(signals.length)}
                </Text>
                <Text style={styles.heroLabel}>active signals</Text>
              </View>
              <View style={styles.heroIcon}>
                <Ionicons color={colors.accent} name="pulse" size={30} />
              </View>
            </View>
            <View style={styles.filterGroup}>
              {signalFilters.map((filter) => (
                <ActionFilter
                  key={filter.key}
                  label={filter.label}
                  selected={selectedFilter === filter.key}
                  onPress={() => setSelectedFilter(filter.key)}
                />
              ))}
            </View>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.state}>
            {signalsQuery.isLoading ? (
              <ActivityIndicator color={colors.primary} />
            ) : (
              <Text style={styles.stateText}>
                {signalsQuery.error
                  ? "信号加载失败"
                  : "暂无活跃信号"}
              </Text>
            )}
          </View>
        }
        refreshControl={
          <RefreshControl
            onRefresh={() => void signalsQuery.refetch()}
            refreshing={signalsQuery.isRefetching}
            tintColor={colors.primary}
          />
        }
        renderItem={({ item }) => <SignalCard signal={item} />}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: colors.background,
    flex: 1,
  },
  listContent: {
    gap: spacing.md,
    padding: spacing.lg,
    paddingBottom: 96,
  },
  header: {
    gap: spacing.md,
  },
  hero: {
    alignItems: "flex-end",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    justifyContent: "space-between",
    padding: spacing.lg,
    ...shadows.panel,
  },
  kicker: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "900",
    textTransform: "uppercase",
  },
  heroValue: {
    color: colors.text,
    fontSize: 38,
    fontWeight: "900",
    lineHeight: 42,
    marginTop: 4,
  },
  heroLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "800",
  },
  heroIcon: {
    alignItems: "center",
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    height: 64,
    justifyContent: "center",
    width: 64,
  },
  filterGroup: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  filterButton: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: spacing.md,
    paddingVertical: 9,
  },
  filterActive: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primaryLine,
  },
  filterText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "800",
  },
  filterTextActive: {
    color: colors.primary,
  },
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
    opacity: 0.72,
    transform: [{ scale: 0.99 }],
  },
  cardHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  category: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "800",
  },
  question: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "800",
    lineHeight: 23,
  },
  metrics: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  metric: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flex: 1,
    gap: 3,
    padding: spacing.md,
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  metricValue: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "800",
  },
  rationale: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 19,
  },
  explanations: {
    gap: spacing.xs,
  },
  explanationRow: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    gap: 3,
    padding: spacing.md,
  },
  explanationLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  explanationValue: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    lineHeight: 18,
  },
  orderButton: {
    alignItems: "center",
    backgroundColor: colors.primary,
    borderColor: colors.primary,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: 7,
    minHeight: 42,
    justifyContent: "center",
  },
  orderText: {
    color: colors.background,
    fontSize: 14,
    fontWeight: "800",
  },
  state: {
    alignItems: "center",
    minHeight: 220,
    justifyContent: "center",
  },
  stateText: {
    color: colors.textMuted,
    fontSize: 14,
    fontWeight: "600",
    textAlign: "center",
  },
});
