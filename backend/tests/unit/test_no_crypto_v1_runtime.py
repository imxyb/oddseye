from __future__ import annotations

from pathlib import Path


def test_crypto_v1_is_not_available_in_runtime_signal_service() -> None:
    source = Path("app/services/signals.py").read_text(encoding="utf-8")

    assert "compute_crypto_signals_v1" not in source
    assert "CryptoThresholdStrategy" not in source
    assert "parse_crypto_threshold" not in source
    assert "crypto_threshold_v1" not in source


def test_strategy_example_only_configures_crypto_threshold_v2() -> None:
    source = Path("../config/strategy.example.yaml").read_text(encoding="utf-8")

    assert "crypto_threshold_v1" not in source
    assert "crypto_threshold_v2" in source
