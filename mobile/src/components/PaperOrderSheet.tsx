import { Ionicons } from "@expo/vector-icons";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import type { OrderSide, PaperOrderRequest } from "../api/types";
import { colors, radius, shadows, spacing } from "../theme";
import { friendlyErrorMessage } from "../utils/errors";
import { actionLabel, sideLabel } from "../utils/labels";

interface PaperOrderSheetProps {
  marketId?: string;
  defaultAccountId?: string;
  defaultLimitPrice?: number | null;
  defaultQuantity?: number;
  onSubmit: (input: PaperOrderRequest) => Promise<unknown> | unknown;
  submitLabel?: string;
}

const sides: OrderSide[] = ["BUY", "SELL", "EXIT"];

export function PaperOrderSheet({
  marketId,
  defaultAccountId = "",
  defaultLimitPrice,
  defaultQuantity = 100,
  onSubmit,
  submitLabel = "提交订单",
}: PaperOrderSheetProps) {
  const [accountId, setAccountId] = useState(defaultAccountId);
  const [editableMarketId, setEditableMarketId] = useState(marketId ?? "");
  const [side, setSide] = useState<OrderSide>("BUY");
  const [outcomeIndex, setOutcomeIndex] = useState(0);
  const [limitPrice, setLimitPrice] = useState(
    defaultLimitPrice ? String(defaultLimitPrice) : "",
  );
  const [quantity, setQuantity] = useState(String(defaultQuantity));
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const activeMarketId = marketId ?? editableMarketId;
  const canSubmit = useMemo(
    () =>
      activeMarketId.trim().length > 0 &&
      Number(limitPrice) > 0 &&
      Number(quantity) > 0,
    [activeMarketId, limitPrice, quantity],
  );

  async function handleSubmit() {
    if (!canSubmit) {
      setError("请补全市场、限价和数量。");
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      await onSubmit({
        account_id: accountId.trim() || null,
        market_id: activeMarketId.trim(),
        side,
        outcome_index: outcomeIndex,
        limit_price: Number(limitPrice),
        quantity: Number(quantity),
      });
    } catch (submitError) {
      setError(friendlyErrorMessage(submitError, "订单创建失败"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.titleRow}>
        <View style={styles.titleIcon}>
          <Ionicons color={colors.primary} name="paper-plane" size={16} />
        </View>
        <Text style={styles.title}>纸上订单</Text>
      </View>

      <View style={styles.segment}>
        {sides.map((value) => (
          <Pressable
            key={value}
            accessibilityRole="button"
            onPress={() => setSide(value)}
            style={[styles.segmentButton, side === value && styles.segmentActive]}
          >
            <Text
              style={[
                styles.segmentText,
                side === value && styles.segmentTextActive,
              ]}
            >
              {actionLabel(value)}
            </Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.segment}>
        {[0, 1].map((value) => (
          <Pressable
            key={value}
            accessibilityRole="button"
            onPress={() => setOutcomeIndex(value)}
            style={[
              styles.segmentButton,
              outcomeIndex === value && styles.segmentActive,
            ]}
          >
            <Text
              style={[
                styles.segmentText,
                outcomeIndex === value && styles.segmentTextActive,
              ]}
            >
              {sideLabel(value === 0 ? "YES" : "NO")}
            </Text>
          </Pressable>
        ))}
      </View>

      <TextInput
        autoCapitalize="none"
        onChangeText={setAccountId}
        placeholder="账户 ID（可选）"
        placeholderTextColor={colors.textMuted}
        style={styles.input}
        value={accountId}
      />

      {!marketId ? (
        <TextInput
          autoCapitalize="none"
          onChangeText={setEditableMarketId}
          placeholder="市场 ID"
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={editableMarketId}
        />
      ) : null}

      <View style={styles.inputRow}>
        <TextInput
          keyboardType="decimal-pad"
          onChangeText={setLimitPrice}
          placeholder="限价"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.flexInput]}
          value={limitPrice}
        />
        <TextInput
          keyboardType="decimal-pad"
          onChangeText={setQuantity}
          placeholder="数量"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.flexInput]}
          value={quantity}
        />
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable
        accessibilityRole="button"
        disabled={isSubmitting}
        onPress={handleSubmit}
        style={({ pressed }) => [
          styles.submit,
          (!canSubmit || isSubmitting) && styles.disabled,
          pressed && styles.pressed,
        ]}
      >
        {isSubmitting ? (
          <ActivityIndicator color={colors.background} />
        ) : (
          <View style={styles.submitContent}>
            <Ionicons color={colors.background} name="checkmark-circle" size={17} />
            <Text style={styles.submitText}>{submitLabel}</Text>
          </View>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
    ...shadows.panel,
  },
  title: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900",
  },
  titleRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.sm,
  },
  titleIcon: {
    alignItems: "center",
    backgroundColor: colors.primarySoft,
    borderColor: colors.primaryLine,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    height: 34,
    justifyContent: "center",
    width: 34,
  },
  segment: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    padding: 3,
  },
  segmentButton: {
    alignItems: "center",
    borderRadius: radius.md,
    flex: 1,
    paddingVertical: 9,
  },
  segmentActive: {
    backgroundColor: colors.primarySoft,
  },
  segmentText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "800",
  },
  segmentTextActive: {
    color: colors.primary,
  },
  input: {
    backgroundColor: colors.backgroundRaised,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    color: colors.text,
    minHeight: 46,
    paddingHorizontal: spacing.md,
  },
  inputRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  flexInput: {
    flex: 1,
  },
  error: {
    color: colors.danger,
    fontSize: 13,
    fontWeight: "600",
  },
  submit: {
    alignItems: "center",
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    minHeight: 48,
    justifyContent: "center",
  },
  disabled: {
    opacity: 0.6,
  },
  pressed: {
    opacity: 0.75,
  },
  submitText: {
    color: colors.background,
    fontSize: 15,
    fontWeight: "800",
  },
  submitContent: {
    alignItems: "center",
    flexDirection: "row",
    gap: 7,
  },
});
