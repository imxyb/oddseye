import { formatCodes, reasonCodeLabel, riskCodeLabel } from "./labels";

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
    rows.push({ label: "依据", value: formatCodes(signal.reason_codes, reasonCodeLabel) });
  }
  if (signal.risk_flags?.length) {
    rows.push({ label: "风险", value: formatCodes(signal.risk_flags, riskCodeLabel) });
  }
  return rows;
}
