import { useQuery } from "@tanstack/react-query";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  getPaperPerformance,
  getPaperPositions,
  paperKeys,
} from "../../src/api/paper";
import { PositionCard } from "../../src/components/PositionCard";
import { colors, spacing } from "../../src/theme";
import { formatCurrency, formatPercent } from "../../src/utils/format";

export default function PortfolioScreen() {
  const performanceQuery = useQuery({
    queryKey: paperKeys.performance,
    queryFn: getPaperPerformance,
  });
  const positionsQuery = useQuery({
    queryKey: paperKeys.positions,
    queryFn: getPaperPositions,
  });

  const positions = positionsQuery.data?.items ?? [];
  const isRefreshing = performanceQuery.isRefetching || positionsQuery.isRefetching;

  function refresh() {
    void performanceQuery.refetch();
    void positionsQuery.refetch();
  }

  return (
    <SafeAreaView edges={["left", "right"]} style={styles.safeArea}>
      <FlatList
        contentContainerStyle={styles.listContent}
        data={positions}
        keyExtractor={(item) => item.position_id ?? item.market_id}
        ListHeaderComponent={
          <View style={styles.summary}>
            <Text style={styles.heading}>Paper account</Text>
            {performanceQuery.isLoading ? (
              <ActivityIndicator color={colors.primary} />
            ) : performanceQuery.data ? (
              <View style={styles.metrics}>
                <View style={styles.metric}>
                  <Text style={styles.metricLabel}>Equity</Text>
                  <Text style={styles.metricValue}>
                    {formatCurrency(performanceQuery.data.equity)}
                  </Text>
                </View>
                <View style={styles.metric}>
                  <Text style={styles.metricLabel}>Cash</Text>
                  <Text style={styles.metricValue}>
                    {formatCurrency(performanceQuery.data.cash)}
                  </Text>
                </View>
                <View style={styles.metric}>
                  <Text style={styles.metricLabel}>Unrealized</Text>
                  <Text style={styles.metricValue}>
                    {formatCurrency(performanceQuery.data.unrealized_pnl)}
                  </Text>
                </View>
                <View style={styles.metric}>
                  <Text style={styles.metricLabel}>Win rate</Text>
                  <Text style={styles.metricValue}>
                    {formatPercent(performanceQuery.data.win_rate)}
                  </Text>
                </View>
              </View>
            ) : (
              <Text style={styles.stateText}>Performance is unavailable.</Text>
            )}
          </View>
        }
        ListEmptyComponent={
          <View style={styles.state}>
            {positionsQuery.isLoading ? (
              <ActivityIndicator color={colors.primary} />
            ) : (
              <Text style={styles.stateText}>
                {positionsQuery.error
                  ? "Could not load positions."
                  : "No open paper positions."}
              </Text>
            )}
          </View>
        }
        refreshControl={
          <RefreshControl
            onRefresh={refresh}
            refreshing={isRefreshing}
            tintColor={colors.primary}
          />
        }
        renderItem={({ item }) => <PositionCard position={item} />}
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
  summary: {
    gap: spacing.md,
  },
  heading: {
    color: colors.text,
    fontSize: 24,
    fontWeight: "900",
  },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metric: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    flexBasis: "48%",
    flexGrow: 1,
    gap: 4,
    padding: spacing.lg,
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  metricValue: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900",
  },
  state: {
    alignItems: "center",
    minHeight: 180,
    justifyContent: "center",
  },
  stateText: {
    color: colors.textMuted,
    fontSize: 14,
    fontWeight: "600",
    textAlign: "center",
  },
});
