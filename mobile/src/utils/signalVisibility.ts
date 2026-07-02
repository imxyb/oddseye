import type { Signal, SignalAction } from "../api/types";

export const DEFAULT_SIGNAL_MIN_EDGE = 0.07;
export const defaultSignalFilterKey = "EDGE";

export type SignalFilterKey = typeof defaultSignalFilterKey | Extract<
  SignalAction,
  "BUY" | "HOLD" | "OBSERVE" | "EXIT" | "REDUCE" | "BLOCKED" | "IGNORE"
>;

export const signalFilters: Array<{ key: SignalFilterKey; label: string }> = [
  { key: defaultSignalFilterKey, label: "优势" },
  { key: "BUY", label: "买入" },
  { key: "HOLD", label: "持有" },
  { key: "OBSERVE", label: "观察" },
  { key: "EXIT", label: "退出" },
  { key: "REDUCE", label: "减仓" },
  { key: "BLOCKED", label: "阻断" },
  { key: "IGNORE", label: "忽略" },
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
