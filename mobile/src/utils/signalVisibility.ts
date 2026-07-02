import type { Signal, SignalAction } from "../api/types";

export const DEFAULT_SIGNAL_MIN_EDGE = 0.07;
export const defaultSignalFilterKey = "EDGE";

export type SignalFilterKey = typeof defaultSignalFilterKey | Extract<
  SignalAction,
  "BUY" | "HOLD" | "OBSERVE" | "EXIT" | "IGNORE"
>;

export const signalFilters: Array<{ key: SignalFilterKey; label: string }> = [
  { key: defaultSignalFilterKey, label: "EDGE" },
  { key: "BUY", label: "BUY" },
  { key: "HOLD", label: "HOLD" },
  { key: "OBSERVE", label: "OBSERVE" },
  { key: "EXIT", label: "EXIT" },
  { key: "IGNORE", label: "IGNORE" },
];

export function signalFilterParams(key: SignalFilterKey): {
  action?: SignalAction;
  minEdge?: number;
} {
  if (key === defaultSignalFilterKey) {
    return { minEdge: DEFAULT_SIGNAL_MIN_EDGE };
  }

  return { action: key };
}

export function isOrderableSignal(
  signal: Pick<Signal, "action" | "side" | "executable_price">,
): boolean {
  return (
    signal.action === "BUY" &&
    (signal.side === "YES" || signal.side === "NO") &&
    typeof signal.executable_price === "number" &&
    Number.isFinite(signal.executable_price) &&
    signal.executable_price > 0
  );
}
