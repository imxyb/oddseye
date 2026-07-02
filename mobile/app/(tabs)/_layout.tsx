import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";
import { View } from "react-native";

import { colors, radius } from "../../src/theme";

const icons = {
  radar: ["radio", "radio-outline"],
  signals: ["pulse", "pulse-outline"],
  portfolio: ["briefcase", "briefcase-outline"],
  settings: ["settings", "settings-outline"],
} as const;

type TabName = keyof typeof icons;

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={({ route }) => {
        const routeName = route.name as TabName;
        const [focusedIcon, idleIcon] = icons[routeName] ?? icons.radar;

        return {
          headerShadowVisible: false,
          headerStyle: { backgroundColor: colors.background },
          headerTintColor: colors.text,
          headerTitleStyle: { fontWeight: "900" },
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.textMuted,
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderColor: colors.borderStrong,
            borderRadius: radius.xl,
            borderTopWidth: 0,
            borderWidth: 1,
            bottom: 12,
            height: 68,
            left: 16,
            paddingBottom: 8,
            paddingTop: 8,
            position: "absolute",
            right: 16,
            shadowColor: colors.shadow,
            shadowOffset: { width: 0, height: 18 },
            shadowOpacity: 0.24,
            shadowRadius: 28,
          },
          tabBarLabelStyle: {
            fontSize: 10,
            fontWeight: "900",
          },
          tabBarIcon: ({ color, focused, size }) => (
            <View
              style={{
                alignItems: "center",
                backgroundColor: focused ? colors.primarySoft : "transparent",
                borderColor: focused ? colors.primaryLine : "transparent",
                borderRadius: 999,
                borderWidth: 1,
                height: 32,
                justifyContent: "center",
                width: 38,
              }}
            >
              <Ionicons
                color={color}
                name={focused ? focusedIcon : idleIcon}
                size={Math.max(19, size - 2)}
              />
            </View>
          ),
        };
      }}
    >
      <Tabs.Screen name="radar" options={{ title: "雷达" }} />
      <Tabs.Screen name="signals" options={{ title: "信号" }} />
      <Tabs.Screen name="portfolio" options={{ title: "账户" }} />
      <Tabs.Screen name="settings" options={{ title: "设置" }} />
    </Tabs>
  );
}
