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
import { MarketCard } from "../../src/components/MarketCard";
import { useFilterStore } from "../../src/stores/filterStore";
import { colors, spacing } from "../../src/theme";
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

  function openMarket(market: RadarMarket) {
    router.push({
      pathname: "/market/[id]",
      params: { id: market.market_id },
    });
  }

  return (
    <SafeAreaView edges={["left", "right"]} style={styles.safeArea}>
      <FlatList
        data={marketsQuery.data?.items ?? []}
        keyExtractor={(item) => item.market_id}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={
          <View style={styles.header}>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={setQuery}
              placeholder="Search markets"
              placeholderTextColor={colors.textMuted}
              style={styles.search}
              value={q}
            />

            <View style={styles.filterGroup}>
              {radarCategories.map((value) => (
                <FilterButton
                  key={value}
                  active={category === value}
                  label={value}
                  onPress={() => setCategory(value)}
                />
              ))}
            </View>

            <View style={styles.filterGroup}>
              {protocols.map((value) => (
                <FilterButton
                  key={value ?? "all"}
                  active={protocol === value}
                  label={value ?? "ALL"}
                  onPress={() => setProtocol(value)}
                />
              ))}
            </View>

            <View style={styles.filterGroup}>
              {sorts.map((value) => (
                <FilterButton
                  key={value}
                  active={sort === value}
                  label={value}
                  onPress={() => setSort(value)}
                />
              ))}
            </View>

            <View style={styles.numberGrid}>
              <NumberFilter
                label="Min quality"
                onChange={(value) => setMinQuality(value ?? 0)}
                placeholder="65"
                value={minQuality}
              />
              <NumberFilter
                label="Min volume"
                onChange={(value) => setMinVolume(value ?? 0)}
                placeholder="500"
                value={minVolume}
              />
              <NumberFilter
                label="Min liquidity"
                onChange={(value) => setMinLiquidity(value ?? 0)}
                placeholder="1000"
                value={minLiquidity}
              />
              <NumberFilter
                label="Max spread"
                onChange={(value) => setMaxSpread(value ?? 0.08)}
                placeholder="0.08"
                value={maxSpread}
              />
              <NumberFilter
                label="Closes hrs"
                onChange={setClosesWithinHours}
                placeholder="Any"
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
                  ? "Could not load radar markets."
                  : "No markets match the current filters."}
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
  },
  header: {
    gap: spacing.md,
  },
  search: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    color: colors.text,
    fontSize: 15,
    minHeight: 48,
    paddingHorizontal: spacing.md,
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
  filterButtonActive: {
    backgroundColor: colors.primary,
  },
  filterText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
  },
  filterTextActive: {
    color: "#ffffff",
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
    textTransform: "uppercase",
  },
  numberInput: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
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
