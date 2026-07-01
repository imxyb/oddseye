import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuthStore } from "../../src/stores/authStore";
import { colors, spacing } from "../../src/theme";

export default function SettingsScreen() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL ?? "Not configured";

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <SafeAreaView edges={["left", "right"]} style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.section}>
          <Text style={styles.heading}>Account</Text>
          <View style={styles.row}>
            <Text style={styles.label}>Username</Text>
            <Text style={styles.value}>{user?.username ?? "-"}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Role</Text>
            <Text style={styles.value}>{user?.role ?? "-"}</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.heading}>API</Text>
          <View style={styles.row}>
            <Text style={styles.label}>Base URL</Text>
            <Text style={styles.value} numberOfLines={2}>
              {apiBaseUrl}
            </Text>
          </View>
        </View>

        <Pressable
          accessibilityRole="button"
          onPress={handleLogout}
          style={({ pressed }) => [styles.logout, pressed && styles.pressed]}
        >
          <Text style={styles.logoutText}>Sign out</Text>
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
  },
  section: {
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
  row: {
    gap: 4,
  },
  label: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  value: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
  },
  logout: {
    alignItems: "center",
    backgroundColor: colors.danger,
    borderRadius: 8,
    minHeight: 50,
    justifyContent: "center",
  },
  pressed: {
    opacity: 0.75,
  },
  logoutText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "800",
  },
});
