# Crypto Threshold V2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `crypto_threshold_v2` for Polymarket-only crypto prediction markets with conservative V2 parsing, probability, execution gates, sizing, lifecycle actions, and automatic simulated paper orders for review/backtesting.

**Architecture:** Add focused `backend/app/strategies/crypto_v2/` modules and wire them through the existing `compute_crypto_signals` service. Reuse existing `ModelSignal`, `PaperAccount`, `PaperOrder`, `PaperFill`, and `PaperPosition` tables, storing full V2 trace in `ModelSignal.raw_json` for the first implementation round.

**Tech Stack:** Python 3.12, SQLAlchemy async ORM, FastAPI service layer, pytest, existing paper trading engine.

---

## Chunk 1: V2 Strategy Core

### Task 1: Parser And Specs

**Files:**
- Create: `backend/app/strategies/crypto_v2/spec.py`
- Create: `backend/app/strategies/crypto_v2/spec_parser.py`
- Test: `backend/tests/strategies/crypto_v2/test_spec_parser.py`

- [ ] Write failing parser tests for close, hit, range, and blocked ambiguity cases.
- [ ] Implement V2 dataclasses and parser.
- [ ] Verify parser tests pass.

### Task 2: Probability And Calibration

**Files:**
- Create: `backend/app/strategies/crypto_v2/probability.py`
- Create: `backend/app/strategies/crypto_v2/calibration.py`
- Test: `backend/tests/strategies/crypto_v2/test_probability.py`

- [ ] Write failing tests for lognormal close/range probability, touch Monte Carlo invariants, deterministic seed, and stress ranges.
- [ ] Implement probability and calibration functions.
- [ ] Verify probability tests pass.

### Task 3: Execution Gate, Sizing, Lifecycle

**Files:**
- Create: `backend/app/strategies/crypto_v2/execution_gate.py`
- Create: `backend/app/strategies/crypto_v2/sizing.py`
- Create: `backend/app/strategies/crypto_v2/lifecycle.py`
- Test: `backend/tests/strategies/crypto_v2/test_execution_gate.py`
- Test: `backend/tests/strategies/crypto_v2/test_sizing.py`
- Test: `backend/tests/strategies/crypto_v2/test_lifecycle.py`

- [ ] Write failing tests for freshness/spread/depth/quality gates, conservative Kelly sizing, and BUY/HOLD/REDUCE/EXIT decisions.
- [ ] Implement gate, sizing, and lifecycle modules.
- [ ] Verify focused tests pass.

## Chunk 2: Service Integration

### Task 4: Data Services And Strategy Orchestrator

**Files:**
- Create: `backend/app/services/crypto_market_data.py`
- Create: `backend/app/services/prediction_orderbook.py`
- Create: `backend/app/strategies/crypto_v2/strategy.py`
- Modify: `backend/app/services/asset_market_data.py`

- [ ] Write failing integration tests with mocked asset data and DB snapshots.
- [ ] Implement snapshot conversion and strategy orchestration.
- [ ] Verify integration tests pass.

### Task 5: Polymarket-Only And Automatic Simulated Orders

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `config/app.example.yaml`
- Modify: `backend/app/services/bootstrap.py`
- Modify: `backend/app/services/ingestion.py`
- Modify: `backend/app/services/signals.py`
- Test: `backend/tests/integration/test_signal_enrichment.py`
- Test: `backend/tests/integration/test_paper_manual_vs_signal_risk.py`

- [ ] Write failing tests proving Kalshi crypto markets are skipped and V2 BUY/EXIT signals auto-create filled simulated orders.
- [ ] Change defaults and service filters to Polymarket-only.
- [ ] Wire V2 signal persistence and automatic paper order execution.
- [ ] Verify backend test subset passes.

## Chunk 3: Verification And Deployment

### Task 6: Full Verification

- [ ] Run focused V2 tests.
- [ ] Run existing backend tests likely affected by config/signals/paper changes.
- [ ] Review git diff against the V2 document and user overrides.

### Task 7: Server Reset And Redeploy

- [ ] Inspect remote deployment state.
- [ ] Upload or pull updated code/config.
- [ ] Stop services.
- [ ] Clear database data intentionally.
- [ ] Run migrations/bootstrap/ingest/signal jobs.
- [ ] Restart services and verify health plus generated V2 signals/orders.
