from backend.services.engine.scripts import quantgpt_real_data_smoke as smoke


KLINE_TABLE = """
| date | open | last | high | low | volume | amount | exchange |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-06-23 | 1239 | 1222.45 | 1264 | 1217 | 58004 | 7179750000 | 0.46 |
| 2026-06-22 | 1214.31 | 1241.41 | 1252.8 | 1205 | 58251 | 7163240000 | 0.47 |
"""


KLINE_TABLE_CHANGED = """
| date | open | last | high | low | volume | amount | exchange |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-06-23 | 1239 | 1223.45 | 1264 | 1217 | 58004 | 7179750000 | 0.46 |
| 2026-06-22 | 1214.31 | 1241.41 | 1252.8 | 1205 | 58251 | 7163240000 | 0.47 |
"""


def test_real_data_smoke_reports_reproducible_repeated_reads(monkeypatch):
    monkeypatch.setattr(
        smoke, "_run_westock_kline", lambda _symbol, _limit: KLINE_TABLE
    )

    result = smoke.run_smoke(["SH600519"], limit=2, repeat=2)

    assert result.status == "passed"
    assert result.reproducible is True
    assert result.repeat_count == 2
    assert result.row_count == 2
    assert result.normalized_symbol_rate == 1.0
    assert result.non_empty_value_rate == 1.0
    assert result.fingerprints["SH600519"]


def test_real_data_smoke_fails_on_repeated_read_mismatch(monkeypatch):
    outputs = iter([KLINE_TABLE, KLINE_TABLE_CHANGED])
    monkeypatch.setattr(
        smoke, "_run_westock_kline", lambda _symbol, _limit: next(outputs)
    )

    result = smoke.run_smoke(["SH600519"], limit=2, repeat=2)

    assert result.status == "failed"
    assert result.reproducible is False
    assert any("fingerprint mismatch" in item for item in result.errors)
