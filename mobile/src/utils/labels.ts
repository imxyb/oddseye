import type { MarketCategory, SignalAction, SignalSide } from "../api/types";

const actionLabels: Record<string, string> = {
  BUY: "买入",
  SELL: "卖出",
  EXIT: "退出",
  REDUCE: "减仓",
  HOLD: "持有",
  OBSERVE: "观察",
  BLOCKED: "阻断",
  IGNORE: "忽略",
};

const sideLabels: Record<string, string> = {
  YES: "YES 结果",
  NO: "NO 结果",
};

const categoryLabels: Record<string, string> = {
  crypto: "加密",
  economics: "宏观",
  finance: "金融",
  watchlist: "自选",
  market: "市场",
};

const sortLabels: Record<string, string> = {
  quality: "质量",
  edge: "优势",
  volume: "成交",
  liquidity: "流动性",
  closingSoon: "临近收盘",
};

const protocolLabels: Record<string, string> = {
  ALL: "全部",
  POLYMARKET: "Polymarket",
  KALSHI: "Kalshi",
};

const statusLabels: Record<string, string> = {
  OPEN: "开放",
  CLOSED: "已关闭",
  RESOLVED: "已结算",
  open: "开放",
  active: "活跃",
  closed: "已关闭",
  settled: "已结算",
};

const riskLabels: Record<string, string> = {
  LOW_LIQUIDITY: "低流动性",
  low_liquidity: "低流动性",
  WIDE_SPREAD: "价差偏宽",
  wide_spread: "价差偏宽",
  NOT_OPEN: "未开放",
  CLOSES_TOO_SOON: "临近收盘",
  closing_soon: "临近收盘",
  RESOLUTION_UNCLEAR: "结算不清晰",
  LOW_MODELABILITY: "模型把握弱",
  QUALITY_BELOW_GATE: "质量偏低",
  PARSER_FAILED: "解析失败",
  PARSER_CONFIDENCE_LOW: "解析置信低",
  YES_ASK_OUT_OF_RANGE: "YES 卖价异常",
  NO_ASK_OUT_OF_RANGE: "NO 卖价异常",
  BARRIER_TOUCH_MODEL_NOT_IMPLEMENTED: "触线模型未启用",
};

const reasonLabels: Record<string, string> = {
  LIQUIDITY_OK: "流动性达标",
  SPREAD_OK: "价差合理",
  MODEL_EDGE_POSITIVE: "模型优势为正",
  BUY_YES_EDGE: "YES 结果有优势",
  BUY_NO_EDGE: "NO 结果有优势",
  EDGE_BELOW_THRESHOLD: "优势不足",
  HOLD_EXISTING_POSITION: "持仓延续",
  EXIT_OPPOSING_MODEL_EDGE: "模型转向",
  CRYPTO_THRESHOLD_TOUCH_MARKET_DETECTED: "触线市场",
  MACRO_V1_MANUAL_ONLY: "宏观需人工确认",
};

const qualityComponentLabels: Record<string, string> = {
  liquidity: "流动性",
  spread: "价差",
  resolution_clarity: "结算清晰度",
  modelability: "可建模性",
  time: "时间",
  activity: "活跃度",
};

export function actionLabel(action?: SignalAction | string | null): string {
  return action ? actionLabels[action] ?? humanizeCode(action) : "无信号";
}

export function sideLabel(side?: SignalSide | string | null): string {
  return side ? sideLabels[side] ?? humanizeCode(side) : "";
}

export function categoryLabel(category?: MarketCategory | string | null): string {
  return category ? categoryLabels[category] ?? humanizeCode(category) : "市场";
}

export function sortLabel(sort: string): string {
  return sortLabels[sort] ?? humanizeCode(sort);
}

export function protocolLabel(protocol?: string | null): string {
  return protocol ? protocolLabels[protocol] ?? protocol : "全部";
}

export function statusLabel(status?: string | null): string {
  return status ? statusLabels[status] ?? humanizeCode(status) : "-";
}

export function riskCodeLabel(code: string): string {
  return riskLabels[code] ?? humanizeCode(code);
}

export function reasonCodeLabel(code: string): string {
  return reasonLabels[code] ?? riskCodeLabel(code);
}

export function qualityComponentLabel(code: string): string {
  return qualityComponentLabels[code] ?? humanizeCode(code);
}

export function formatCodes(
  codes: string[] | null | undefined,
  formatter: (code: string) => string,
): string {
  return codes?.length ? codes.map(formatter).join(" · ") : "-";
}

function humanizeCode(value: string): string {
  return value.replace(/[_-]+/g, " ");
}
