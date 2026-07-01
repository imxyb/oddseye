import { StyleSheet, Text, View } from "react-native";
import Svg, { Line, Polyline } from "react-native-svg";

import type { MarketBar } from "../api/types";
import { colors, spacing } from "../theme";
import { chartRange } from "../utils/probability";

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
        <Text style={styles.emptyText}>No probability history yet</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
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
          stroke={colors.primary}
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
          <Text style={styles.legendText}>YES</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.swatch, { backgroundColor: colors.info }]} />
          <Text style={styles.legendText}>NO</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    padding: spacing.md,
  },
  empty: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    justifyContent: "center",
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
