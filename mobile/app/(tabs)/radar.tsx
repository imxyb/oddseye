import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useMemo } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { getRadarMarkets, radarKeys } from "../../src/api/radar";
import type { Protocol, RadarMarket } from "../../src/api/types";
import { shortCountLabel } from "../../src/brand";
import { MarketCard } from "../../src/components/MarketCard";
import { useFilterStore } from "../../src/stores/filterStore";
import { colors, radius, shadows, spacing } from "../../src/theme";
import { categoryLabel, protocolLabel, sortLabel } from "../../src/utils/labels";
import { radarCategories } from "../../src/utils/radarFilters";

const protocols: Array<Protocol | undefined> = [undefined, "POLYMARKET", "KALSHI"];
const sorts = ["quality", "edge", "volume", "liquidity", "closingSoon"] as const;

function FilterButton({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.filterButton, active && styles.filterButtonActive]}
    >
      <Text style={[styles.filterText, active && styles.filterTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

function NumberFilter({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: number | undefined;
  onChange: (value: number | undefined) => void;
  placeholder: string;
}) {
  return (
    <View style={styles.numberFilter}>
      <Text style={styles.numberLabel}>{label}</Text>
      <TextInput
        keyboardType="decimal-pad"
        onChangeText={(text) => onChange(text.trim() ? Number(text) : undefined)}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        style={styles.numberInput}
        value={value === undefined ? "" : String(value)}
      />
    </View>
  );
}

export default function RadarScreen() {
  const {
    category,
    protocol,
    sort,
    minQuality,
    minVolume,
    minLiquidity,
    maxSpread,
    closesWithinHours,
    q,
    setCategory,
    setProtocol,
    setSort,
    setMinQuality,
    setMinVolume,
    setMinLiquidity,
    setMaxSpread,
    setClosesWithinHours,
    setQuery,
  } = useFilterStore();

  const params = useMemo(
    () => ({
      category,
      protocol,
      q: q.trim() || undefined,
      sort,
      minQuality,
      minVolume,
      minLiquidity,
      maxSpread,
      closesWithinHours,
      limit: 50,
    }),
    [category, closesWithinHours, maxSpread, minLiquidity, minQuality, minVolume, protocol, q, sort],
  );

  const marketsQuery = useQuery({
    queryKey: radarKeys.markets(params),
    queryFn: () => getRadarMarkets(params),
  });
  const markets = marketsQuery.data?.items ?? [];

  function openMarket(market: RadarMarket) {
    router.push({
      pathname: "/market/[id]",
      params: { id: market.market_id },
    });
  }

  return (
    <SafeAreaView edges={["left", "right"]} style={styles.safeArea}>
      <FlatList
        data={markets}
        keyExtractor={(item) => item.market_id}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={
          <View style={styles.header}>
            <View style={styles.hero}>
              <View>
                <Text style={styles.kicker}>Live edge</Text>
                <Text style={styles.heroValue}>
                  {marketsQuery.isLoading ? "..." : shortCountLabel(markets.length)}
                </Text>
                <Text style={styles.heroLabel}>markets on deck</Text>
              </View>
              <View style={styles.gauge}>
                <Text style={styles.gaugeValue}>{minQuality || 65}</Text>
                <Text style={styles.gaugeLabel}>min Q</Text>
              </View>
            </View>

            <View style={styles.searchWrap}>
              <Ionicons color={colors.textSubtle} name="search" size={17} />
              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                onChangeText={setQuery}
                placeholder="Search market"
                placeholderTextColor={colors.textSubtle}
                style={styles.search}
                value={q}
              />
              <Ionicons color={colors.primary} name="filter" size={17} />
            </View>

            <View style={styles.filterGroup}>
              {radarCategories.map((value) => (
                <FilterButton
                  key={value}
                  active={category === value}
                  label={categoryLabel(value)}
                  onPress={() => setCategory(value)}
                />
              ))}
            </View>

            <View style={styles.filterGroup}>
              {protocols.map((value) => (
                <FilterButton
                  key={value ?? "all"}
                  active={protocol === value}
                  label={protocolLabel(value)}
                  onPress={() => setProtocol(value)}
                />
              ))}
            </View>

            <View style={styles.filterGroup}>
              {sorts.map((value) => (
                <FilterButton
                  key={value}
                  active={sort === value}
                  label={sortLabel(value)}
                  onPress={() => setSort(value)}
                />
              ))}
            </View>

            <View style={styles.numberGrid}>
              <NumberFilter
                label="质量"
                onChange={(value) => setMinQuality(value ?? 0)}
                placeholder="65"
                value={minQuality}
              />
              <NumberFilter
                label="成交"
                onChange={(value) => setMinVolume(value ?? 0)}
                placeholder="500"
                value={minVolume}
              />
              <NumberFilter
                label="流动性"
                onChange={(value) => setMinLiquidity(value ?? 0)}
                placeholder="1000"
                value={minLiquidity}
              />
              <NumberFilter
                label="价差"
                onChange={(value) => setMaxSpread(value ?? 0.08)}
                placeholder="0.08"
                value={maxSpread}
              />
              <NumberFilter
                label="收盘"
                onChange={setClosesWithinHours}
                placeholder="不限"
                value={closesWithinHours}
              />
            </View>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.state}>
            {marketsQuery.isLoading ? (
              <ActivityIndicator color={colors.primary} />
            ) : (
              <Text style={styles.stateText}>
                {marketsQuery.error
                  ? "雷达加载失败"
                  : "当前筛选暂无市场"}
              </Text>
            )}
          </View>
        }
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            onRefresh={() => void marketsQuery.refetch()}
            refreshing={marketsQuery.isRefetching}
            tintColor={colors.primary}
          />
        }
        renderItem={({ item }) => (
          <MarketCard market={item} onPress={() => openMarket(item)} />
        )}
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
    overflow: "hidden",
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
  gauge: {
    alignItems: "center",
    backgroundColor: colors.primarySoft,
    borderColor: colors.primaryLine,
    borderRadius: 999,
    borderWidth: 8,
    height: 76,
    justifyContent: "center",
    width: 76,
  },
  gaugeValue: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "900",
  },
  gaugeLabel: {
    color: colors.primary,
    fontSize: 9,
    fontWeight: "900",
    textTransform: "uppercase",
  },
  searchWrap: {
    alignItems: "center",
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: spacing.sm,
    minHeight: 46,
    paddingHorizontal: spacing.md,
  },
  search: {
    color: colors.text,
    flex: 1,
    fontSize: 15,
    minHeight: 44,
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
  filterButtonActive: {
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
  numberGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  numberFilter: {
    flexBasis: "31%",
    flexGrow: 1,
    gap: 4,
    minWidth: 104,
  },
  numberLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  numberInput: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    color: colors.text,
    minHeight: 42,
    paddingHorizontal: spacing.sm,
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
