import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AppLogo } from "../src/components/AppLogo";
import { useAuthStore } from "../src/stores/authStore";
import { colors, radius, shadows, spacing } from "../src/theme";
import { friendlyErrorMessage } from "../src/utils/errors";

export default function LoginScreen() {
  const login = useAuthStore((state) => state.login);
  const storeError = useAuthStore((state) => state.error);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function handleLogin() {
    if (!username.trim() || !password) {
      setLocalError("请输入用户名和密码。");
      return;
    }

    setIsSubmitting(true);
    setLocalError(null);

    try {
      await login(username.trim(), password);
      router.replace("/(tabs)/radar");
    } catch (error) {
      setLocalError(friendlyErrorMessage(error, "登录失败"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.container}
      >
        <View style={styles.header}>
          <AppLogo size={82} />
          <Text style={styles.kicker}>私有策略台</Text>
          <Text style={styles.title}>OddsEye</Text>
          <Text style={styles.subtitle}>预测市场雷达 · Paper command deck</Text>
        </View>

        <View style={styles.form}>
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            onChangeText={setUsername}
            placeholder="用户名"
            placeholderTextColor={colors.textMuted}
            style={styles.input}
            textContentType="username"
            value={username}
          />
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            onChangeText={setPassword}
            placeholder="密码"
            placeholderTextColor={colors.textMuted}
            secureTextEntry
            style={styles.input}
            textContentType="password"
            value={password}
          />

          {localError || storeError ? (
            <Text style={styles.error}>{localError ?? storeError}</Text>
          ) : null}

          <Pressable
            accessibilityRole="button"
            disabled={isSubmitting}
            onPress={handleLogin}
            style={({ pressed }) => [
              styles.button,
              isSubmitting && styles.disabled,
              pressed && styles.pressed,
            ]}
          >
            {isSubmitting ? (
              <ActivityIndicator color={colors.background} />
            ) : (
              <View style={styles.buttonContent}>
                <Ionicons color={colors.background} name="scan-circle" size={18} />
                <Text style={styles.buttonText}>进入工作台</Text>
              </View>
            )}
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: colors.background,
    flex: 1,
  },
  container: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.xl,
  },
  header: {
    alignItems: "flex-start",
    gap: spacing.sm,
    marginBottom: spacing.xl,
  },
  kicker: {
    alignSelf: "flex-start",
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    color: colors.accent,
    fontSize: 12,
    fontWeight: "900",
    overflow: "hidden",
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  title: {
    color: colors.text,
    fontSize: 34,
    fontWeight: "900",
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 16,
    lineHeight: 23,
  },
  form: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.md,
    padding: spacing.lg,
    ...shadows.panel,
  },
  input: {
    backgroundColor: colors.backgroundRaised,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    color: colors.text,
    fontSize: 16,
    minHeight: 52,
    paddingHorizontal: spacing.lg,
  },
  error: {
    color: colors.danger,
    fontSize: 13,
    fontWeight: "600",
  },
  button: {
    alignItems: "center",
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    minHeight: 52,
    justifyContent: "center",
  },
  disabled: {
    opacity: 0.65,
  },
  pressed: {
    opacity: 0.78,
  },
  buttonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: "800",
  },
  buttonContent: {
    alignItems: "center",
    flexDirection: "row",
    gap: 8,
  },
});
