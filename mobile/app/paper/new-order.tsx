import { Ionicons } from "@expo/vector-icons";
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
import { colors, radius, shadows, spacing } from "../../src/theme";
import { friendlyErrorMessage } from "../../src/utils/errors";

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
      setLocalError("请填写名义金额和限价。");
      return;
    }

    setLocalError(null);
    await mutation.mutateAsync();
  }

  return (
    <View style={styles.card}>
      <View style={styles.titleRow}>
        <View style={styles.titleIcon}>
          <Ionicons color={colors.primary} name="flash" size={16} />
        </View>
        <Text style={styles.heading}>信号下单</Text>
      </View>
      <Text style={styles.subtle}>信号 {signalId}</Text>

      <TextInput
        autoCapitalize="none"
        onChangeText={setAccountId}
        placeholder="账户 ID（可选）"
        placeholderTextColor={colors.textMuted}
        style={styles.input}
        value={accountId}
      />
      <View style={styles.inputRow}>
        <TextInput
          keyboardType="decimal-pad"
          onChangeText={setNotional}
          placeholder="名义金额"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.flexInput]}
          value={notional}
        />
        <TextInput
          keyboardType="decimal-pad"
          onChangeText={setLimitPrice}
          placeholder="限价"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.flexInput]}
          value={limitPrice}
        />
      </View>

      {localError || mutation.error ? (
        <Text style={styles.error}>
          {localError ??
            friendlyErrorMessage(mutation.error, "信号订单创建失败")}
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
          <ActivityIndicator color={colors.background} />
        ) : (
          <View style={styles.submitContent}>
            <Ionicons color={colors.background} name="checkmark-circle" size={17} />
            <Text style={styles.submitText}>按信号下单</Text>
          </View>
        )}
      </Pressable>

      {mutation.isSuccess ? (
        <Text style={styles.success}>订单已提交</Text>
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
          <Text style={styles.success}>订单已提交</Text>
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
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
    ...shadows.panel,
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
  success: {
    color: colors.success,
    fontSize: 14,
    fontWeight: "700",
  },
});
