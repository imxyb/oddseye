import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { getSettingsUsage, settingsKeys } from "../../src/api/settings";
import { AppLogo } from "../../src/components/AppLogo";
import { useAuthStore } from "../../src/stores/authStore";
import { colors, radius, shadows, spacing } from "../../src/theme";
import { buildSettingsInfoRows } from "../../src/utils/settingsInfo";

export default function SettingsScreen() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL ?? "未配置";
  const settingsQuery = useQuery({
    queryKey: settingsKeys.usage,
    queryFn: getSettingsUsage,
  });
  const apiRows = buildSettingsInfoRows(apiBaseUrl, settingsQuery.data);

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <SafeAreaView edges={["left", "right"]} style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <AppLogo size={56} />
          <View style={styles.heroCopy}>
            <Text style={styles.kicker}>OddsEye</Text>
            <Text style={styles.heading}>账户</Text>
          </View>
        </View>

        <View style={styles.section}>
          <View style={styles.row}>
            <Text style={styles.label}>用户名</Text>
            <Text style={styles.value}>{user?.username ?? "-"}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>角色</Text>
            <Text style={styles.value}>{user?.role ?? "-"}</Text>
          </View>
        </View>

        <View style={styles.section}>
          <View style={styles.sectionTitleRow}>
            <Ionicons color={colors.info} name="server" size={18} />
            <Text style={styles.sectionTitle}>系统</Text>
          </View>
          {apiRows.map((row) => (
            <View key={row.label} style={styles.row}>
              <Text style={styles.label}>{row.label}</Text>
              <Text style={styles.value} numberOfLines={3}>
                {row.value}
              </Text>
            </View>
          ))}
        </View>

        <Pressable
          accessibilityRole="button"
          onPress={handleLogout}
          style={({ pressed }) => [styles.logout, pressed && styles.pressed]}
        >
          <Ionicons color={colors.danger} name="log-out" size={18} />
          <Text style={styles.logoutText}>退出登录</Text>
        </Pressable>
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
    paddingBottom: 96,
  },
  hero: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: spacing.md,
    padding: spacing.lg,
    ...shadows.panel,
  },
  heroCopy: {
    gap: 3,
  },
  kicker: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "900",
    textTransform: "uppercase",
  },
  section: {
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
    fontSize: 22,
    fontWeight: "900",
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900",
  },
  sectionTitleRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.sm,
  },
  row: {
    gap: 4,
  },
  label: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  value: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
  },
  logout: {
    alignItems: "center",
    backgroundColor: colors.dangerSoft,
    borderColor: colors.danger,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    gap: spacing.sm,
    minHeight: 50,
    justifyContent: "center",
  },
  pressed: {
    opacity: 0.75,
  },
  logoutText: {
    color: colors.danger,
    fontSize: 15,
    fontWeight: "800",
  },
});
