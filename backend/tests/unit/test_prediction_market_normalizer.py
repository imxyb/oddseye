from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.normalizer.prediction_market import parse_ts


@pytest.mark.parametrize("value", [1_767_225_600, 1_767_225_600_000])
def test_parse_ts_accepts_unix_timestamps(value: int) -> None:
    assert parse_ts(value) == datetime.fromtimestamp(1_767_225_600, tz=UTC)
