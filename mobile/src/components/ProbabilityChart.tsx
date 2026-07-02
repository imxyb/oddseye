import { StyleSheet, Text, View } from "react-native";
import Svg, { Defs, Line, LinearGradient, Path, Polyline, Stop } from "react-native-svg";

import type { MarketBar } from "../api/types";
import { colors, radius, shadows, spacing } from "../theme";
import { chartRange } from "../utils/probability";
import { sideLabel } from "../utils/labels";

interface ProbabilityChartProps {
  bars: MarketBar[];
  height?: number;
}

function linePoints(
  bars: MarketBar[],
  getValue: (bar: MarketBar) => number | undefined,
  width: number,
  height: number,
) {
  if (bars.length < 2) {
    return "";
  }

  const [min, max] = chartRange(bars);
  const span = max - min || 1;

  return bars
    .map((bar, index) => {
      const x = (index / (bars.length - 1)) * width;
      const rawValue = getValue(bar) ?? 0;
      const y = height - ((rawValue - min) / span) * height;
      return `${x},${Math.max(0, Math.min(height, y))}`;
    })
    .join(" ");
}

export function ProbabilityChart({ bars, height = 180 }: ProbabilityChartProps) {
  const width = 320;

  if (!bars.length) {
    return (
      <View style={[styles.empty, { height }]}>
        <Text style={styles.emptyText}>暂无概率走势</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
        <Defs>
          <LinearGradient id="yesLine" x1="0" x2="1" y1="0" y2="0">
            <Stop offset="0" stopColor={colors.accent} />
            <Stop offset="0.5" stopColor={colors.primary} />
            <Stop offset="1" stopColor={colors.info} />
          </LinearGradient>
        </Defs>
        <Path
          d={`M0 ${height - 1} L0 ${height * 0.72} C80 ${height * 0.55} 118 ${height * 0.82} 164 ${height * 0.48} S246 ${height * 0.36} ${width} ${height * 0.24} L${width} ${height - 1} Z`}
          fill={colors.primarySoft}
          opacity={0.55}
        />
        <Line
          x1="0"
          x2={width}
          y1={height / 2}
          y2={height / 2}
          stroke={colors.border}
          strokeDasharray="4 6"
          strokeWidth="1"
        />
        <Polyline
          fill="none"
          points={linePoints(bars, (bar) => bar.yes.c, width, height)}
          stroke="url(#yesLine)"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
        <Polyline
          fill="none"
          points={linePoints(bars, (bar) => bar.no?.c, width, height)}
          stroke={colors.info}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
      </Svg>
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.swatch, { backgroundColor: colors.primary }]} />
          <Text style={styles.legendText}>{sideLabel("YES")}</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.swatch, { backgroundColor: colors.info }]} />
          <Text style={styles.legendText}>{sideLabel("NO")}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    padding: spacing.md,
    ...shadows.panel,
  },
  empty: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    justifyContent: "center",
    ...shadows.panel,
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: "600",
  },
  legend: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  legendItem: {
    alignItems: "center",
    flexDirection: "row",
    gap: 6,
  },
  legendText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  swatch: {
    borderRadius: 3,
    height: 6,
    width: 18,
  },
});
