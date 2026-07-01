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
import { colors, spacing } from "../../src/theme";
import { buildFreshnessNotice } from "../../src/utils/freshness";
import {
  formatCents,
  formatCurrency,
  formatDate,
  formatPercent,
} from "../../src/utils/format";
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
          {marketQuery.error ? "Could not load market." : "Market not found."}
        </Text>
      </View>
    );
  }

  return (
    <SafeAreaView edges={["left", "right", "bottom"]} style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View style={styles.metaRow}>
            <Text style={styles.meta}>{market.protocol}</Text>
            <Text style={styles.meta}>{market.category}</Text>
            <Text style={styles.meta}>Quality {market.market_quality_score ?? "-"}</Text>
          </View>
          <Text style={styles.title}>{market.question}</Text>
          <View style={styles.metaRow}>
            <Text style={styles.subtle}>Close {formatDate(market.closes_at)}</Text>
            <Text style={styles.subtle}>Status {market.status}</Text>
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
              <Text style={styles.refreshText}>Refresh market</Text>
            </Pressable>
          </View>
        </View>

        {refreshMutation.error ? (
          <Text style={styles.error}>
            {refreshMutation.error instanceof Error
              ? refreshMutation.error.message
              : "Could not refresh market."}
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
            <Text style={styles.metricLabel}>YES bid</Text>
            <Text style={styles.metricValue}>{formatCents(yes?.bid)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>YES ask</Text>
            <Text style={styles.metricValue}>{formatCents(yes?.ask)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>NO bid</Text>
            <Text style={styles.metricValue}>{formatCents(no?.bid)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>NO ask</Text>
            <Text style={styles.metricValue}>{formatCents(no?.ask)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>Implied</Text>
            <Text style={styles.metricValue}>{formatCents(yesProbability(market))}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>Signal edge</Text>
            <Text style={styles.metricValue}>
              {formatPercent(market.latest_signal?.edge)}
            </Text>
          </View>
        </View>

        <View style={styles.marketStats}>
          <Text style={styles.stat}>Liquidity {formatCurrency(market.liquidity_usd)}</Text>
          <Text style={styles.stat}>24h volume {formatCurrency(market.volume_usd_24h)}</Text>
          <Text style={styles.stat}>OI {formatCurrency(market.open_interest_usd)}</Text>
        </View>

        <RiskFlags market={market} />

        {market.quality ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Quality</Text>
            <View style={styles.qualityGrid}>
              {Object.entries(market.quality.components).map(([key, value]) => (
                <View key={key} style={styles.qualityMetric}>
                  <Text style={styles.metricLabel}>{key.replace(/_/g, " ")}</Text>
                  <Text style={styles.metricValue}>{Math.round(value)}</Text>
                </View>
              ))}
            </View>
            <View style={styles.reasonRow}>
              {market.quality.reason_codes.map((code) => (
                <Text key={code} style={styles.reasonPill}>
                  {code.replace(/_/g, " ")}
                </Text>
              ))}
              {market.quality.risk_flags.map((flag) => (
                <Text key={flag} style={[styles.reasonPill, styles.riskPill]}>
                  {flag.replace(/_/g, " ")}
                </Text>
              ))}
            </View>
          </View>
        ) : null}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Probability</Text>
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
            <Text style={styles.sectionTitle}>Current position</Text>
            <PositionCard position={market.current_position} />
          </View>
        ) : null}

        <PaperOrderSheet
          defaultLimitPrice={midpoint(yes)}
          marketId={market.market_id}
          onSubmit={(input) => orderMutation.mutateAsync(input)}
        />

        {orderMutation.isSuccess ? (
          <Text style={styles.success}>Paper order submitted.</Text>
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
    gap: spacing.md,
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
    borderRadius: 6,
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "800",
    paddingHorizontal: 8,
    paddingVertical: 5,
    textTransform: "uppercase",
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
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: 6,
    minHeight: 34,
    paddingHorizontal: 10,
    paddingVertical: 7,
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
    borderRadius: 8,
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
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    flexBasis: "31%",
    flexGrow: 1,
    gap: 4,
    minWidth: 104,
    padding: spacing.md,
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
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
  stat: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: "700",
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
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    flexBasis: "31%",
    flexGrow: 1,
    gap: 4,
    minWidth: 104,
    padding: spacing.md,
  },
  reasonRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  reasonPill: {
    backgroundColor: colors.successSoft,
    borderRadius: 999,
    color: colors.success,
    fontSize: 11,
    fontWeight: "800",
    overflow: "hidden",
    paddingHorizontal: 9,
    paddingVertical: 6,
    textTransform: "uppercase",
  },
  riskPill: {
    backgroundColor: colors.warningSoft,
    color: colors.warning,
  },
  chartLoading: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    minHeight: 210,
    justifyContent: "center",
  },
  success: {
    color: colors.success,
    fontSize: 14,
    fontWeight: "700",
  },
});
