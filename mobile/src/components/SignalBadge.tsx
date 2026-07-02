import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import type { SignalAction, SignalSide } from "../api/types";
import { colors } from "../theme";
import { actionLabel, sideLabel } from "../utils/labels";

interface SignalBadgeProps {
  action?: SignalAction | string | null;
  side?: SignalSide | string | null;
  compact?: boolean;
}

type IoniconName = keyof typeof Ionicons.glyphMap;

function paletteFor(action?: string | null): {
  backgroundColor: string;
  color: string;
  icon: IoniconName;
} {
  switch (action) {
    case "BUY":
      return {
        backgroundColor: colors.successSoft,
        color: colors.success,
        icon: "arrow-up-circle",
      };
    case "SELL":
    case "EXIT":
      return {
        backgroundColor: colors.dangerSoft,
        color: colors.danger,
        icon: "arrow-down-circle",
      };
    case "HOLD":
    case "OBSERVE":
      return {
        backgroundColor: colors.infoSoft,
        color: colors.info,
        icon: "eye",
      };
    case "IGNORE":
      return {
        backgroundColor: colors.surfaceMuted,
        color: colors.textMuted,
        icon: "remove-circle",
      };
    default:
      return {
        backgroundColor: colors.warningSoft,
        color: colors.warning,
        icon: "alert-circle",
      };
  }
}

export function SignalBadge({ action, side, compact = false }: SignalBadgeProps) {
  const palette = paletteFor(action ?? undefined);
  const label = [actionLabel(action), sideLabel(side)].filter(Boolean).join(" ");

  return (
    <View
      style={[
        styles.badge,
        compact && styles.compactBadge,
        {
          backgroundColor: palette.backgroundColor,
          borderColor: palette.color,
        },
      ]}
    >
      <Ionicons
        color={palette.color}
        name={palette.icon}
        size={compact ? 12 : 14}
      />
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
    alignItems: "center",
    alignSelf: "flex-start",
    flexDirection: "row",
    gap: 5,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    minHeight: 28,
    paddingHorizontal: 10,
  },
  compactBadge: {
    minHeight: 25,
    paddingHorizontal: 8,
  },
  text: {
    fontSize: 12,
    fontWeight: "900",
  },
  compactText: {
    fontSize: 11,
  },
});
