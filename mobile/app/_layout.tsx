import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AppLogo } from "../src/components/AppLogo";
import { useAuthStore } from "../src/stores/authStore";
import { colors, spacing } from "../src/theme";

function AuthBootstrapper() {
  const router = useRouter();
  const segments = useSegments();
  const bootstrap = useAuthStore((state) => state.bootstrap);
  const isBootstrapped = useAuthStore((state) => state.isBootstrapped);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (!isBootstrapped) {
      return;
    }

    const rootSegment = segments[0];
    const isLoginRoute = rootSegment === "login";

    if (!isAuthenticated && !isLoginRoute) {
      router.replace("/login");
      return;
    }

    if (isAuthenticated && (isLoginRoute || !rootSegment)) {
      router.replace("/(tabs)/radar");
    }
  }, [isAuthenticated, isBootstrapped, router, segments]);

  if (!isBootstrapped) {
    return (
      <View pointerEvents="auto" style={styles.bootOverlay}>
        <AppLogo size={72} />
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return null;
}

export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000,
          },
        },
      }),
  );

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            contentStyle: { backgroundColor: colors.background },
            headerStyle: { backgroundColor: colors.background },
            headerShadowVisible: false,
            headerTintColor: colors.text,
            headerTitleStyle: { fontWeight: "900" },
          }}
        >
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="login" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="market/[id]" options={{ title: "市场详情" }} />
          <Stack.Screen name="paper/new-order" options={{ title: "纸上下单" }} />
        </Stack>
        <AuthBootstrapper />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  bootOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    backgroundColor: colors.background,
    gap: spacing.xl,
    justifyContent: "center",
  },
});
