# Command Deck UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Command Deck UI redesign and new OddsEye logo assets.

**Architecture:** Keep the current Expo Router structure and React Native `StyleSheet` styling. Add a small pure brand module for shared logo asset paths and visual tone helpers, plus a React Native SVG logo component for screens.

**Tech Stack:** Expo 54, React Native 0.81, Expo Router, React Query, Zustand, `@expo/vector-icons`, `react-native-svg`, Vitest.

---

## Files

- Create: `mobile/src/brand.ts`
- Create: `mobile/src/__tests__/brand.test.ts`
- Create: `mobile/src/components/AppLogo.tsx`
- Create: `mobile/assets/oddseye-logo.svg`
- Create: `mobile/assets/icon.png`
- Create: `mobile/assets/adaptive-icon.png`
- Modify: `mobile/app.json`
- Modify: `mobile/src/theme.ts`
- Modify: `mobile/app/_layout.tsx`
- Modify: `mobile/app/(tabs)/_layout.tsx`
- Modify: `mobile/app/login.tsx`
- Modify: `mobile/app/(tabs)/radar.tsx`
- Modify: `mobile/app/(tabs)/signals.tsx`
- Modify: `mobile/app/(tabs)/portfolio.tsx`
- Modify: `mobile/app/(tabs)/settings.tsx`
- Modify: `mobile/app/market/[id].tsx`
- Modify: `mobile/app/paper/new-order.tsx`
- Modify: shared components under `mobile/src/components/`

## Tasks

- [ ] Write failing brand tests for logo asset paths and quality tone mapping.
- [ ] Implement the brand helper module and pass the tests.
- [ ] Create the vector app logo and raster app icon assets.
- [ ] Update Expo app icon configuration.
- [ ] Apply the Command Deck theme tokens.
- [ ] Redesign shared logo, badges, flags, cards, chart, and order sheet.
- [ ] Redesign app screens around compact metrics and icon-first controls.
- [ ] Run targeted tests, full mobile tests, typecheck, and Expo smoke verification.
