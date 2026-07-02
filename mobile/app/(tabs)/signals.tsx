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
import type { Signal, SignalAction } from "../../src/api/types";
import { SignalBadge } from "../../src/components/SignalBadge";
import { colors, spacing } from "../../src/theme";
import { formatCents, formatPercent } from "../../src/utils/format";
import { buildSignalExplanationRows } from "../../src/utils/signalExplanation";

const signalActions: Array<SignalAction | undefined> = [
  undefined,
  "BUY",
  "OBSERVE",
  "EXIT",
  "IGNORE",
  "HOLD",
];

function ActionFilter({
  action,
  selected,
  onPress,
}: {
  action: SignalAction | undefined;
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
        {action ?? "ALL"}
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
        <Text style={styles.category}>{signal.category ?? "market"}</Text>
      </View>

      <Text style={styles.question} numberOfLines={3}>
        {signal.question}
      </Text>

      <View style={styles.metrics}>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>Edge</Text>
          <Text style={styles.metricValue}>{formatPercent(signal.edge)}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>Confidence</Text>
          <Text style={styles.metricValue}>
            {formatPercent(signal.confidence)}
          </Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>Limit</Text>
          <Text style={styles.metricValue}>
            {formatCents(signal.executable_price)}
          </Text>
        </View>
      </View>

      {signal.rationale ? (
        <Text style={styles.rationale} numberOfLines={3}>
          {signal.rationale}
        </Text>
      ) : null}

      {explanationRows.length > 0 ? (
        <View style={styles.explanations}>
          {explanationRows.map((row) => (
            <View key={row.label} style={styles.explanationRow}>
              <Text style={styles.explanationLabel}>{row.label}</Text>
              <Text style={styles.explanationValue} numberOfLines={2}>
                {row.value}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      <Pressable
        accessibilityRole="button"
        onPress={() =>
          router.push({
            pathname: "/paper/new-order",
            params: {
              signalId: signal.signal_id,
              limitPrice: signal.executable_price
                ? String(signal.executable_price)
                : "",
            },
          })
        }
        style={styles.orderButton}
      >
        <Text style={styles.orderText}>Paper order</Text>
      </Pressable>
    </Pressable>
  );
}

export default function SignalsScreen() {
  const [selectedAction, setSelectedAction] = useState<SignalAction | undefined>();
  const params = useMemo(
    () => ({
      action: selectedAction,
      limit: 50,
    }),
    [selectedAction],
  );
  const signalsQuery = useQuery({
    queryKey: signalKeys.list(params),
    queryFn: () => getSignals(params),
  });

  return (
    <SafeAreaView edges={["left", "right"]} style={styles.safeArea}>
      <FlatList
        contentContainerStyle={styles.listContent}
        data={signalsQuery.data?.items ?? []}
        keyExtractor={(item) => item.signal_id}
        ListHeaderComponent={
          <View style={styles.filterGroup}>
            {signalActions.map((action) => (
              <ActionFilter
                key={action ?? "all"}
                action={action}
                selected={selectedAction === action}
                onPress={() => setSelectedAction(action)}
              />
            ))}
          </View>
        }
        ListEmptyComponent={
          <View style={styles.state}>
            {signalsQuery.isLoading ? (
              <ActivityIndicator color={colors.primary} />
            ) : (
              <Text style={styles.stateText}>
                {signalsQuery.error
                  ? "Could not load signals."
                  : "No active signals yet."}
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
  },
  filterGroup: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  filterButton: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: 9,
  },
  filterActive: {
    backgroundColor: colors.primary,
  },
  filterText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "800",
  },
  filterTextActive: {
    color: colors.surface,
  },
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
  cardHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  category: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
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
    borderRadius: 8,
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
    borderRadius: 8,
    gap: 3,
    padding: spacing.md,
  },
  explanationLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  explanationValue: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    lineHeight: 18,
  },
  orderButton: {
    alignItems: "center",
    backgroundColor: colors.primarySoft,
    borderRadius: 8,
    minHeight: 42,
    justifyContent: "center",
  },
  orderText: {
    color: colors.primary,
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
