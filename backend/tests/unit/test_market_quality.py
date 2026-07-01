from datetime import datetime, timedelta, timezone

from app.scoring.market_quality import (
    QualityInputs,
    activity_score,
    compute_market_quality,
    liquidity_score,
    spread_score,
)


def test_subscores_follow_documented_boundaries() -> None:
    assert liquidity_score(None) == 0
    assert liquidity_score(1_000) == 0
    assert liquidity_score(50_000) == 100
    assert spread_score(None) == 0
    assert spread_score(0.02) == 100
    assert spread_score(0.10) == 0
    assert activity_score(20_000, 200) == 100


def test_quality_score_reaches_paper_trading_gate_for_clear_liquid_crypto_market() -> None:
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = compute_market_quality(
        QualityInputs(
            question="Will BTC be above $80000 on July 31, 2026?",
            description="This market resolves according to the listed venue rules once the BTC "
            "reference price is observed at the settlement time.",
            categories=["crypto"],
            status="OPEN",
            venue_url="https://example.com/market/btc",
            closes_at=now + timedelta(days=25),
            resolves_at=now + timedelta(days=30),
            liquidity_usd=25_000,
            spread_ct=0.03,
            volume_usd_24h=12_000,
            trades_24h=150,
        ),
        now=now,
    )

    assert result.score >= 65
    assert result.passes_paper_gate is True
    assert "LIQUIDITY_OK" in result.reason_codes
    assert result.components["modelability"] >= 60


def test_quality_score_blocks_ambiguous_wide_spread_market_from_auto_paper_trading() -> None:
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = compute_market_quality(
        QualityInputs(
            question="Will a major crypto event happen substantially soon?",
            description="Vague market.",
            categories=["crypto"],
            status="OPEN",
            venue_url=None,
            closes_at=now + timedelta(days=2),
            resolves_at=None,
            liquidity_usd=900,
            spread_ct=0.12,
            volume_usd_24h=200,
            trades_24h=8,
        ),
        now=now,
    )

    assert result.score < 65
    assert result.passes_paper_gate is False
    assert "WIDE_SPREAD" in result.risk_flags
    assert "LOW_LIQUIDITY" in result.risk_flags

