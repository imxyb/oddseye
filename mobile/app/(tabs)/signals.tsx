import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
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
import { SignalBadge } from "../../src/components/SignalBadge";
import { colors, spacing } from "../../src/theme";
import { formatCents, formatPercent } from "../../src/utils/format";

function SignalCard({ signal }: { signal: Signal }) {
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
  const params = { limit: 50 };
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
