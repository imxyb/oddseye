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
import { colors, spacing } from "../theme";

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
  submitLabel = "Create paper order",
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
      setError("Fill market, limit price, and quantity.");
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
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Could not create order",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Paper order</Text>

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
              {value}
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
              {value === 0 ? "YES" : "NO"}
            </Text>
          </Pressable>
        ))}
      </View>

      <TextInput
        autoCapitalize="none"
        onChangeText={setAccountId}
        placeholder="Account ID (optional)"
        placeholderTextColor={colors.textMuted}
        style={styles.input}
        value={accountId}
      />

      {!marketId ? (
        <TextInput
          autoCapitalize="none"
          onChangeText={setEditableMarketId}
          placeholder="Market ID"
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={editableMarketId}
        />
      ) : null}

      <View style={styles.inputRow}>
        <TextInput
          keyboardType="decimal-pad"
          onChangeText={setLimitPrice}
          placeholder="Limit price"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.flexInput]}
          value={limitPrice}
        />
        <TextInput
          keyboardType="decimal-pad"
          onChangeText={setQuantity}
          placeholder="Quantity"
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
          <ActivityIndicator color="#ffffff" />
        ) : (
          <Text style={styles.submitText}>{submitLabel}</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
  },
  title: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "800",
  },
  segment: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    flexDirection: "row",
    padding: 3,
  },
  segmentButton: {
    alignItems: "center",
    borderRadius: 6,
    flex: 1,
    paddingVertical: 9,
  },
  segmentActive: {
    backgroundColor: colors.surface,
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
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: 8,
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
    borderRadius: 8,
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
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "800",
  },
});
