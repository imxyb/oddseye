export type Protocol = "POLYMARKET" | "KALSHI";
export type MarketCategory = "crypto" | "economics" | "finance" | "watchlist";
export type MarketStatus = "OPEN" | "CLOSED" | "RESOLVED" | string;
export type SignalAction = "BUY" | "SELL" | "EXIT" | "HOLD" | "OBSERVE" | "IGNORE";
export type SignalSide = "YES" | "NO";
export type OrderSide = "BUY" | "SELL" | "EXIT";

export interface User {
  username: string;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: User;
}

export interface MarketOutcome {
  index: number;
  label: string;
  bid: number | null;
  ask: number | null;
  spread: number | null;
}

export interface SignalSummary {
  action: SignalAction;
  side?: SignalSide;
  edge?: number | null;
  confidence?: number | null;
}

export interface QualityExplanation {
  components: Record<string, number>;
  reason_codes: string[];
  risk_flags: string[];
  passes_paper_gate: boolean;
}

export interface RadarMarket {
  market_id: string;
  event_id?: string;
  protocol: Protocol | string;
  category: MarketCategory | string;
  question: string;
  status: MarketStatus;
  closes_at?: string | null;
  resolves_at?: string | null;
  outcomes: MarketOutcome[];
  liquidity_usd?: number | null;
  volume_usd_24h?: number | null;
  open_interest_usd?: number | null;
  market_quality_score?: number | null;
  quality?: QualityExplanation | null;
  latest_signal?: SignalSummary | null;
  risk_flags?: string[];
}

export interface RadarMarketsResponse {
  items: RadarMarket[];
  total: number;
}

export interface MarketBar {
  t: number;
  yes: { o: number; h: number; l: number; c: number };
  no?: { o: number; h: number; l: number; c: number };
  yes_bid?: number | null;
  yes_ask?: number | null;
  volume_usd?: number | null;
  open_interest_usd?: number | null;
  trades?: number | null;
}

export interface MarketBarsResponse {
  market_id: string;
  bars: MarketBar[];
}

export interface MarketDetail extends RadarMarket {
  description?: string | null;
  current_position?: PaperPosition | null;
}

export interface Signal {
  signal_id: string;
  market_id: string;
  question: string;
  category?: MarketCategory | string;
  action: SignalAction;
  side?: SignalSide;
  edge?: number | null;
  confidence?: number | null;
  model_probability?: number | null;
  executable_price?: number | null;
  rationale?: string | null;
  created_at?: string | null;
}

export interface SignalsResponse {
  items: Signal[];
  total?: number;
}

export interface PaperOrderRequest {
  account_id?: string | null;
  market_id: string;
  side: OrderSide;
  outcome_index: number;
  limit_price: number;
  quantity: number;
}

export interface SignalPaperOrderRequest {
  account_id?: string | null;
  notional: number;
  limit_price: number;
}

export interface PaperOrder {
  order_id?: string;
  status?: string;
  market_id?: string;
}

export interface PaperPosition {
  position_id?: string;
  market_id: string;
  question?: string;
  outcome_index: number;
  outcome_label?: string;
  quantity: number;
  avg_price: number;
  mark_price?: number | null;
  unrealized_pnl?: number | null;
  realized_pnl?: number | null;
  opened_at?: string | null;
}

export interface PaperPositionsResponse {
  items: PaperPosition[];
}

export interface PaperPerformance {
  equity: number;
  cash: number;
  unrealized_pnl: number;
  realized_pnl: number;
  win_rate: number;
  max_drawdown: number;
  total_trades: number;
}
