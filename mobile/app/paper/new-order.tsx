import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { createPaperOrder, paperKeys } from "../../src/api/paper";
import { createPaperOrderFromSignal } from "../../src/api/signals";
import type { PaperOrderRequest } from "../../src/api/types";
import { PaperOrderSheet } from "../../src/components/PaperOrderSheet";
import { colors, spacing } from "../../src/theme";

function SignalOrderForm({
  signalId,
  defaultLimitPrice,
}: {
  signalId: string;
  defaultLimitPrice?: string;
}) {
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState("");
  const [notional, setNotional] = useState("100");
  const [limitPrice, setLimitPrice] = useState(defaultLimitPrice ?? "");
  const [localError, setLocalError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createPaperOrderFromSignal(signalId, {
        account_id: accountId.trim() || null,
        notional: Number(notional),
        limit_price: Number(limitPrice),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: paperKeys.positions });
      void queryClient.invalidateQueries({ queryKey: paperKeys.performance });
    },
  });

  async function submit() {
    if (Number(notional) <= 0 || Number(limitPrice) <= 0) {
      setLocalError("Fill notional and limit price.");
      return;
    }

    setLocalError(null);
    await mutation.mutateAsync();
  }

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Signal paper order</Text>
      <Text style={styles.subtle}>Signal ID {signalId}</Text>

      <TextInput
        autoCapitalize="none"
        onChangeText={setAccountId}
        placeholder="Account ID (optional)"
        placeholderTextColor={colors.textMuted}
        style={styles.input}
        value={accountId}
      />
      <View style={styles.inputRow}>
        <TextInput
          keyboardType="decimal-pad"
          onChangeText={setNotional}
          placeholder="Notional"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.flexInput]}
          value={notional}
        />
        <TextInput
          keyboardType="decimal-pad"
          onChangeText={setLimitPrice}
          placeholder="Limit price"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.flexInput]}
          value={limitPrice}
        />
      </View>

      {localError || mutation.error ? (
        <Text style={styles.error}>
          {localError ??
            (mutation.error instanceof Error
              ? mutation.error.message
              : "Could not create signal order")}
        </Text>
      ) : null}

      <Pressable
        accessibilityRole="button"
        onPress={() => void submit()}
        style={({ pressed }) => [
          styles.submit,
          mutation.isPending && styles.disabled,
          pressed && styles.pressed,
        ]}
      >
        {mutation.isPending ? (
          <ActivityIndicator color="#ffffff" />
        ) : (
          <Text style={styles.submitText}>Create from signal</Text>
        )}
      </Pressable>

      {mutation.isSuccess ? (
        <Text style={styles.success}>Paper order submitted.</Text>
      ) : null}
    </View>
  );
}

export default function NewPaperOrderScreen() {
  const params = useLocalSearchParams<{
    marketId?: string;
    signalId?: string;
    limitPrice?: string;
  }>();
  const queryClient = useQueryClient();
  const marketId = Array.isArray(params.marketId)
    ? params.marketId[0]
    : params.marketId;
  const signalId = Array.isArray(params.signalId)
    ? params.signalId[0]
    : params.signalId;
  const limitPrice = Array.isArray(params.limitPrice)
    ? params.limitPrice[0]
    : params.limitPrice;

  const manualMutation = useMutation({
    mutationFn: (input: PaperOrderRequest) => createPaperOrder(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: paperKeys.positions });
      void queryClient.invalidateQueries({ queryKey: paperKeys.performance });
    },
  });

  return (
    <SafeAreaView edges={["left", "right", "bottom"]} style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        {signalId ? (
          <SignalOrderForm
            defaultLimitPrice={limitPrice}
            signalId={signalId}
          />
        ) : (
          <PaperOrderSheet
            defaultLimitPrice={limitPrice ? Number(limitPrice) : undefined}
            marketId={marketId}
            onSubmit={(input) => manualMutation.mutateAsync(input)}
          />
        )}

        {manualMutation.isSuccess ? (
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
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
  },
  heading: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "900",
  },
  subtle: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: "600",
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
  success: {
    color: colors.success,
    fontSize: 14,
    fontWeight: "700",
  },
});
