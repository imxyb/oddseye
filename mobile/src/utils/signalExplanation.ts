export interface SignalExplanationSource {
  reason_codes?: string[] | null;
  risk_flags?: string[] | null;
}

export interface SignalExplanationRow {
  label: string;
  value: string;
}

export function buildSignalExplanationRows(
  signal: SignalExplanationSource,
): SignalExplanationRow[] {
  const rows: SignalExplanationRow[] = [];
  if (signal.reason_codes?.length) {
    rows.push({ label: "Reason", value: signal.reason_codes.join(", ") });
  }
  if (signal.risk_flags?.length) {
    rows.push({ label: "Risk", value: signal.risk_flags.join(", ") });
  }
  return rows;
}
