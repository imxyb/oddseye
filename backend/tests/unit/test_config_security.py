from __future__ import annotations

import pytest

from app.core.config import get_settings


def test_prod_rejects_short_jwt_secret(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("JWT_SECRET", "short")
    monkeypatch.setenv("APP_CONFIG_PATH", str(tmp_path / "missing.yaml"))
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="JWT_SECRET"):
        get_settings()

    get_settings.cache_clear()


def test_runtime_config_loads_crypto_threshold_v2_strategy_section(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
strategies:
  crypto_threshold_v1:
    enabled: true
  crypto_threshold_v2:
    enabled: true
    mode: paper_only
    legacy_v1_enabled: false
    parser:
      min_confidence: 0.91
      touch_min_confidence: 0.94
    edge:
      max_spread_ct: 0.015
      min_exec_edge: 0.08
    sizing:
      min_notional: 7
      default_paper_notional_cap: 33
      max_position_pct: 0.005
      max_asset_horizon_exposure_pct: 0.011
    paper_execution:
      auto_execute_signals: false
    real_execution:
      enabled: false
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("APP_ENV", "dev")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.config.strategies.crypto_threshold_v1.enabled is False
    assert settings.config.strategies.crypto_threshold_v2.enabled is True
    assert settings.config.strategies.crypto_threshold_v2.mode == "paper_only"
    assert settings.config.strategies.crypto_threshold_v2.parser.min_confidence == 0.91
    assert settings.config.strategies.crypto_threshold_v2.edge.max_spread_ct == 0.015
    assert settings.config.strategies.crypto_threshold_v2.sizing.min_notional == 7
    assert (
        settings.config.strategies.crypto_threshold_v2.sizing.max_asset_horizon_exposure_pct
        == 0.011
    )
    assert settings.config.strategies.crypto_threshold_v2.paper_execution.auto_execute_signals is False

    get_settings.cache_clear()


def test_runtime_config_loads_sibling_strategy_example_when_app_yaml_has_no_strategies(
    monkeypatch,
    tmp_path,
) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
app:
  name: production-config
""",
        encoding="utf-8",
    )
    (tmp_path / "strategy.example.yaml").write_text(
        """
crypto_threshold_v2:
  enabled: true
  mode: observe_only
  edge:
    max_spread_ct: 0.012
  paper_execution:
    auto_execute_signals: false
macro_calendar_v1:
  enabled: true
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("STRATEGY_CONFIG_PATH", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.config.app.name == "production-config"
    assert settings.config.strategies.crypto_threshold_v2.mode == "observe_only"
    assert settings.config.strategies.crypto_threshold_v2.edge.max_spread_ct == 0.012
    assert settings.config.strategies.crypto_threshold_v2.paper_execution.auto_execute_signals is False

    get_settings.cache_clear()
