import { Ionicons } from "@expo/vector-icons";
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
  getPaperReview,
  paperKeys,
} from "../../src/api/paper";
import { AppLogo } from "../../src/components/AppLogo";
import { PositionCard } from "../../src/components/PositionCard";
import { colors, radius, shadows, spacing } from "../../src/theme";
import { buildPerformanceMetrics } from "../../src/utils/paperPerformance";
import {
  buildReviewRollupSections,
  buildTradeTraceRows,
} from "../../src/utils/paperReview";

export default function PortfolioScreen() {
  const performanceQuery = useQuery({
    queryKey: paperKeys.performance,
    queryFn: getPaperPerformance,
  });
  const positionsQuery = useQuery({
    queryKey: paperKeys.positions,
    queryFn: getPaperPositions,
  });
  const reviewQuery = useQuery({
    queryKey: paperKeys.review,
    queryFn: getPaperReview,
  });

  const positions = positionsQuery.data?.items ?? [];
  const reviewSections = reviewQuery.data
    ? buildReviewRollupSections(reviewQuery.data)
    : [];
  const tradeRows = reviewQuery.data ? buildTradeTraceRows(reviewQuery.data.trades) : [];
  const isRefreshing =
    performanceQuery.isRefetching ||
    positionsQuery.isRefetching ||
    reviewQuery.isRefetching;

  function refresh() {
    void performanceQuery.refetch();
    void positionsQuery.refetch();
    void reviewQuery.refetch();
  }

  return (
    <SafeAreaView edges={["left", "right"]} style={styles.safeArea}>
      <FlatList
        contentContainerStyle={styles.listContent}
        data={positions}
        keyExtractor={(item) => item.position_id ?? item.market_id}
        ListHeaderComponent={
          <View style={styles.headerContent}>
            <View style={styles.hero}>
              <View style={styles.brandRow}>
                <AppLogo size={48} />
                <View>
                  <Text style={styles.kicker}>Paper deck</Text>
                  <Text style={styles.heading}>纸上账户</Text>
                </View>
              </View>
              <Ionicons color={colors.info} name="wallet" size={28} />
            </View>
            {performanceQuery.isLoading ? (
              <ActivityIndicator color={colors.primary} />
            ) : performanceQuery.data ? (
              <View style={styles.metrics}>
                {buildPerformanceMetrics(performanceQuery.data).map((metric) => (
                  <View key={metric.label} style={styles.metric}>
                    <View style={styles.metricHeader}>
                      <Ionicons color={colors.textMuted} name="stats-chart" size={13} />
                      <Text style={styles.metricLabel}>{metric.label}</Text>
                    </View>
                    <Text style={styles.metricValue}>{metric.value}</Text>
                  </View>
                ))}
              </View>
            ) : (
              <Text style={styles.stateText}>账户数据暂不可用</Text>
            )}

            <View style={styles.reviewGroup}>
              {reviewSections.map((section) => (
                <View key={section.title} style={styles.reviewSection}>
                  <Text style={styles.sectionHeading}>{section.title}</Text>
                  {section.items.length > 0 ? (
                    section.items.slice(0, 3).map((item) => (
                      <View key={item.key} style={styles.reviewItem}>
                        <Text style={styles.reviewKey} numberOfLines={1}>
                          {item.key}
                        </Text>
                        <View style={styles.reviewMetrics}>
                          {item.metrics.map((metric) => (
                            <View key={metric.label} style={styles.reviewMetric}>
                              <Text style={styles.reviewMetricLabel}>
                                {metric.label}
                              </Text>
                              <Text style={styles.reviewMetricValue}>
                                {metric.value}
                              </Text>
                            </View>
                          ))}
                        </View>
                      </View>
                    ))
                  ) : (
                    <Text style={styles.stateText}>暂无复盘数据</Text>
                  )}
                </View>
              ))}

              <View style={styles.reviewSection}>
                <Text style={styles.sectionHeading}>成交追踪</Text>
                {tradeRows.length > 0 ? (
                  tradeRows.map((trade) => (
                    <View key={trade.id} style={styles.tradeRow}>
                      <View style={styles.tradeMain}>
                        <Text style={styles.tradeTitle} numberOfLines={2}>
                          {trade.title}
                        </Text>
                        <Text style={styles.tradeSubtitle} numberOfLines={1}>
                          {trade.subtitle}
                        </Text>
                      </View>
                      <View style={styles.traceMeta}>
                        <Text style={styles.price}>{trade.price}</Text>
                        <Text style={styles.traceText} numberOfLines={1}>
                          信号 {trade.signal}
                        </Text>
                        <Text style={styles.traceText} numberOfLines={1}>
                          快照 {trade.snapshot}
                        </Text>
                        <Text style={styles.traceText} numberOfLines={1}>
                          {trade.strategy}
                        </Text>
                      </View>
                    </View>
                  ))
                ) : (
                  <Text style={styles.stateText}>暂无成交记录</Text>
                )}
              </View>
            </View>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.state}>
            {positionsQuery.isLoading ? (
              <ActivityIndicator color={colors.primary} />
            ) : (
              <Text style={styles.stateText}>
                {positionsQuery.error
                  ? "持仓加载失败"
                  : "暂无持仓"}
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
    paddingBottom: 96,
  },
  headerContent: {
    gap: spacing.md,
  },
  hero: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    justifyContent: "space-between",
    padding: spacing.lg,
    ...shadows.panel,
  },
  brandRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.md,
  },
  kicker: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "900",
    textTransform: "uppercase",
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
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flexBasis: "48%",
    flexGrow: 1,
    gap: 4,
    padding: spacing.lg,
    ...shadows.panel,
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  metricHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: 5,
  },
  metricValue: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900",
  },
  reviewGroup: {
    gap: spacing.lg,
    marginTop: spacing.sm,
  },
  reviewSection: {
    gap: spacing.sm,
  },
  sectionHeading: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "900",
  },
  reviewItem: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.sm,
    padding: spacing.md,
    ...shadows.panel,
  },
  reviewKey: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900",
  },
  reviewMetrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  reviewMetric: {
    minWidth: 82,
  },
  reviewMetricLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  reviewMetricValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800",
  },
  tradeRow: {
    alignItems: "flex-start",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: spacing.md,
    padding: spacing.md,
    ...shadows.panel,
  },
  tradeMain: {
    flex: 1,
    gap: 4,
    minWidth: 0,
  },
  tradeTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800",
  },
  tradeSubtitle: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  traceMeta: {
    alignItems: "flex-end",
    gap: 3,
    maxWidth: 140,
  },
  price: {
    color: colors.primary,
    fontSize: 16,
    fontWeight: "900",
  },
  traceText: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
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
