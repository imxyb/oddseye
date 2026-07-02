import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  getMarket,
  getMarketBars,
  marketKeys,
  refreshMarket,
} from "../../src/api/markets";
import { createPaperOrder, paperKeys } from "../../src/api/paper";
import type { PaperOrderRequest } from "../../src/api/types";
import { PaperOrderSheet } from "../../src/components/PaperOrderSheet";
import { PositionCard } from "../../src/components/PositionCard";
import { ProbabilityChart } from "../../src/components/ProbabilityChart";
import { RiskFlags } from "../../src/components/RiskFlags";
import { SignalBadge } from "../../src/components/SignalBadge";
import { colors, radius, shadows, spacing } from "../../src/theme";
import { buildFreshnessNotice } from "../../src/utils/freshness";
import { friendlyErrorMessage } from "../../src/utils/errors";
import {
  formatCents,
  formatCurrency,
  formatDate,
  formatPercent,
} from "../../src/utils/format";
import {
  categoryLabel,
  protocolLabel,
  qualityComponentLabel,
  reasonCodeLabel,
  riskCodeLabel,
  sideLabel,
  statusLabel,
} from "../../src/utils/labels";
import { midpoint, yesProbability } from "../../src/utils/probability";

export default function MarketDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const marketId = Array.isArray(id) ? id[0] : id;
  const queryClient = useQueryClient();

  const marketQuery = useQuery({
    queryKey: marketKeys.detail(marketId),
    queryFn: () => getMarket(marketId),
    enabled: Boolean(marketId),
  });

  const barsQuery = useQuery({
    queryKey: marketKeys.bars(marketId, { range: "7d", resolution: "hour1" }),
    queryFn: () =>
      getMarketBars(marketId, { range: "7d", resolution: "hour1" }),
    enabled: Boolean(marketId),
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshMarket(marketId),
    onSuccess: (response) => {
      queryClient.setQueryData(marketKeys.detail(marketId), response.market);
      void queryClient.invalidateQueries({
        queryKey: ["markets", marketId, "bars"],
      });
      void queryClient.invalidateQueries({ queryKey: ["radar"] });
    },
  });

  const orderMutation = useMutation({
    mutationFn: (input: PaperOrderRequest) => createPaperOrder(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: paperKeys.positions });
      void queryClient.invalidateQueries({ queryKey: paperKeys.performance });
    },
  });

  const market = marketQuery.data;
  const yes = market?.outcomes.find((outcome) => outcome.index === 0);
  const no = market?.outcomes.find((outcome) => outcome.index === 1);
  const freshnessNotice = buildFreshnessNotice(market?.freshness);

  if (marketQuery.isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  if (!market) {
    return (
      <View style={styles.center}>
        <Text style={styles.stateText}>
          {marketQuery.error ? "市场加载失败" : "未找到市场"}
        </Text>
      </View>
    );
  }

  return (
    <SafeAreaView edges={["left", "right", "bottom"]} style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View style={styles.metaRow}>
            <Text style={styles.meta}>{protocolLabel(market.protocol)}</Text>
            <Text style={styles.meta}>{categoryLabel(market.category)}</Text>
            <Text style={styles.meta}>质量 {market.market_quality_score ?? "-"}</Text>
          </View>
          <Text style={styles.title}>{market.question}</Text>
          <View style={styles.metaRow}>
            <Text style={styles.subtle}>收盘 {formatDate(market.closes_at)}</Text>
            <Text style={styles.subtle}>状态 {statusLabel(market.status)}</Text>
          </View>
          <View style={styles.actionRow}>
            <SignalBadge
              action={market.latest_signal?.action}
              side={market.latest_signal?.side}
            />
            <Pressable
              accessibilityRole="button"
              disabled={refreshMutation.isPending}
              onPress={() => void refreshMutation.mutateAsync()}
              style={({ pressed }) => [
                styles.refreshButton,
                pressed && styles.pressed,
                refreshMutation.isPending && styles.disabled,
              ]}
            >
              {refreshMutation.isPending ? (
                <ActivityIndicator color={colors.primary} size="small" />
              ) : (
                <Ionicons
                  color={colors.primary}
                  name="refresh"
                  size={16}
                />
              )}
              <Text style={styles.refreshText}>刷新</Text>
            </Pressable>
          </View>
        </View>

        {refreshMutation.error ? (
          <Text style={styles.error}>
            {friendlyErrorMessage(refreshMutation.error, "刷新失败")}
          </Text>
        ) : null}

        {freshnessNotice ? (
          <View style={styles.warning}>
            <Text style={styles.warningTitle}>{freshnessNotice.title}</Text>
            <Text style={styles.warningText}>{freshnessNotice.detail}</Text>
          </View>
        ) : null}

        <View style={styles.priceGrid}>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>{sideLabel("YES")} 买价</Text>
            <Text style={styles.metricValue}>{formatCents(yes?.bid)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>{sideLabel("YES")} 卖价</Text>
            <Text style={styles.metricValue}>{formatCents(yes?.ask)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>{sideLabel("NO")} 买价</Text>
            <Text style={styles.metricValue}>{formatCents(no?.bid)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>{sideLabel("NO")} 卖价</Text>
            <Text style={styles.metricValue}>{formatCents(no?.ask)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>隐含概率</Text>
            <Text style={styles.metricValue}>{formatCents(yesProbability(market))}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>信号优势</Text>
            <Text style={styles.metricValue}>
              {formatPercent(market.latest_signal?.edge)}
            </Text>
          </View>
        </View>

        <View style={styles.marketStats}>
          <View style={styles.statPill}>
            <Ionicons color={colors.textMuted} name="water" size={12} />
            <Text style={styles.stat}>{formatCurrency(market.liquidity_usd)}</Text>
          </View>
          <View style={styles.statPill}>
            <Ionicons color={colors.textMuted} name="pulse" size={12} />
            <Text style={styles.stat}>{formatCurrency(market.volume_usd_24h)}</Text>
          </View>
          <View style={styles.statPill}>
            <Ionicons color={colors.textMuted} name="layers" size={12} />
            <Text style={styles.stat}>{formatCurrency(market.open_interest_usd)}</Text>
          </View>
        </View>

        <RiskFlags market={market} />

        {market.quality ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>质量拆解</Text>
            <View style={styles.qualityGrid}>
              {Object.entries(market.quality.components).map(([key, value]) => (
                <View key={key} style={styles.qualityMetric}>
                  <Text style={styles.metricLabel}>{qualityComponentLabel(key)}</Text>
                  <Text style={styles.metricValue}>{Math.round(value)}</Text>
                </View>
              ))}
            </View>
            <View style={styles.reasonRow}>
              {market.quality.reason_codes.map((code) => (
                <Text key={code} style={styles.reasonPill}>
                  {reasonCodeLabel(code)}
                </Text>
              ))}
              {market.quality.risk_flags.map((flag) => (
                <Text key={flag} style={[styles.reasonPill, styles.riskPill]}>
                  {riskCodeLabel(flag)}
                </Text>
              ))}
            </View>
          </View>
        ) : null}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>概率走势</Text>
          {barsQuery.isLoading ? (
            <View style={styles.chartLoading}>
              <ActivityIndicator color={colors.primary} />
            </View>
          ) : (
            <ProbabilityChart bars={barsQuery.data?.bars ?? []} />
          )}
        </View>

        {market.current_position ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>当前持仓</Text>
            <PositionCard position={market.current_position} />
          </View>
        ) : null}

        <PaperOrderSheet
          defaultLimitPrice={midpoint(yes)}
          marketId={market.market_id}
          onSubmit={(input) => orderMutation.mutateAsync(input)}
        />

        {orderMutation.isSuccess ? (
          <Text style={styles.success}>订单已提交</Text>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: colors.background,
    flex: 1,
  },
  content: {
    gap: spacing.lg,
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  center: {
    alignItems: "center",
    backgroundColor: colors.background,
    flex: 1,
    justifyContent: "center",
    padding: spacing.xl,
  },
  stateText: {
    color: colors.textMuted,
    fontSize: 15,
    fontWeight: "600",
    textAlign: "center",
  },
  header: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
    ...shadows.panel,
  },
  actionRow: {
    alignItems: "center",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  meta: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "800",
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  title: {
    color: colors.text,
    fontSize: 26,
    fontWeight: "900",
    lineHeight: 33,
  },
  subtle: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: "600",
  },
  refreshButton: {
    alignItems: "center",
    backgroundColor: colors.primarySoft,
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: 6,
    minHeight: 34,
    paddingHorizontal: 10,
    paddingVertical: 7,
    ...shadows.panel,
  },
  refreshText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
  },
  disabled: {
    opacity: 0.55,
  },
  pressed: {
    opacity: 0.75,
  },
  error: {
    color: colors.danger,
    fontSize: 13,
    fontWeight: "700",
  },
  warning: {
    backgroundColor: colors.warningSoft,
    borderColor: colors.warning,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    gap: 4,
    padding: spacing.md,
  },
  warningTitle: {
    color: colors.warning,
    fontSize: 13,
    fontWeight: "900",
  },
  warningText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "600",
    lineHeight: 18,
  },
  priceGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metric: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flexBasis: "31%",
    flexGrow: 1,
    gap: 4,
    minWidth: 104,
    padding: spacing.md,
    ...shadows.panel,
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  metricValue: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "900",
  },
  marketStats: {
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
    minHeight: 28,
    paddingHorizontal: 9,
  },
  stat: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "800",
  },
  section: {
    gap: spacing.md,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "900",
  },
  qualityGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  qualityMetric: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flexBasis: "31%",
    flexGrow: 1,
    gap: 4,
    minWidth: 104,
    padding: spacing.md,
    ...shadows.panel,
  },
  reasonRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  reasonPill: {
    backgroundColor: colors.successSoft,
    borderColor: colors.success,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    color: colors.success,
    fontSize: 11,
    fontWeight: "800",
    overflow: "hidden",
    paddingHorizontal: 9,
    paddingVertical: 6,
  },
  riskPill: {
    backgroundColor: colors.warningSoft,
    borderColor: colors.warning,
    color: colors.warning,
  },
  chartLoading: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    minHeight: 210,
    justifyContent: "center",
    ...shadows.panel,
  },
  success: {
    color: colors.success,
    fontSize: 14,
    fontWeight: "700",
  },
});
