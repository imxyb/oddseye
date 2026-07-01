import { StyleSheet, Text, View } from "react-native";

import type { SignalAction, SignalSide } from "../api/types";
import { colors } from "../theme";

interface SignalBadgeProps {
  action?: SignalAction | string | null;
  side?: SignalSide | string | null;
  compact?: boolean;
}

function paletteFor(action?: string | null) {
  switch (action) {
    case "BUY":
      return { backgroundColor: colors.successSoft, color: colors.success };
    case "SELL":
    case "EXIT":
      return { backgroundColor: colors.dangerSoft, color: colors.danger };
    case "HOLD":
    case "OBSERVE":
      return { backgroundColor: colors.infoSoft, color: colors.info };
    case "IGNORE":
      return { backgroundColor: colors.surfaceMuted, color: colors.textMuted };
    default:
      return { backgroundColor: colors.warningSoft, color: colors.warning };
  }
}

export function SignalBadge({ action, side, compact = false }: SignalBadgeProps) {
  const palette = paletteFor(action ?? undefined);
  const label = [action ?? "NO SIGNAL", side].filter(Boolean).join(" ");

  return (
    <View style={[styles.badge, { backgroundColor: palette.backgroundColor }]}>
      <Text
        style={[
          styles.text,
          compact && styles.compactText,
          { color: palette.color },
        ]}
      >
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  text: {
    fontSize: 12,
    fontWeight: "700",
  },
  compactText: {
    fontSize: 11,
  },
});
