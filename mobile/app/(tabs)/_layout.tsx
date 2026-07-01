import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";

import { colors } from "../../src/theme";

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
          headerTitleStyle: { fontWeight: "800" },
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.textMuted,
          tabBarStyle: {
            borderTopColor: colors.border,
          },
          tabBarIcon: ({ color, focused, size }) => (
            <Ionicons
              color={color}
              name={focused ? focusedIcon : idleIcon}
              size={size}
            />
          ),
        };
      }}
    >
      <Tabs.Screen name="radar" options={{ title: "Radar" }} />
      <Tabs.Screen name="signals" options={{ title: "Signals" }} />
      <Tabs.Screen name="portfolio" options={{ title: "Portfolio" }} />
      <Tabs.Screen name="settings" options={{ title: "Settings" }} />
    </Tabs>
  );
}
