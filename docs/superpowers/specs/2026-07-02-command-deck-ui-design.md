# Command Deck UI Design

## Goal

Redesign the Expo mobile app into a premium dark command deck for prediction-market scanning and paper trading.

## Direction

The approved direction is `Command Deck`: dense but calm, with fewer explanatory labels, stronger iconography, compact metric cards, short pills, mini trend lines, and a new OddsEye mark.

## Scope

- Refresh global colors, spacing, radii, and shadows in `mobile/src/theme.ts`.
- Add a reusable app logo/brand mark and project app icon assets.
- Update login, tabs, radar, signals, portfolio, settings, market detail, and paper order surfaces.
- Refine shared cards and badges so the main information is readable at a glance.

## Logo Concept

The new mark combines an eye, radar crosshair, and probability curve. It should work as a small app icon, a login brand mark, and a compact header glyph without relying on text.

## Constraints

- Keep the existing Expo/React Native stack and `@expo/vector-icons`.
- Do not add a heavy design-system dependency.
- Keep Chinese UI labels where they are primary navigation or actions.
- Avoid long instructional text inside the app.
- Preserve existing API flows and data behavior.
