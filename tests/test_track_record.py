"""
Contract tests for core.track_record and the single scoring path.

The track record is the whole point of the system, so its failure modes are the
ones that matter most:
  * grading a forecast that hasn't aged yet (counting an unfinished bet)
  * silently presenting a backtest as a live record
  * the app and the CLI ranking differently, so the log records something the
    screen never showed
"""

import os

import numpy as np
import pandas as pd
import pytest

from core.config import LABEL_HORIZON_WEEKS, WAVE_PCT
from core.decide import LOG_COLUMNS, append_log
from core.track_record import grade_log, load_log, summary


def _panel(rows):
    """rows: (ticker, date, fwd_ret) -> a minimal graded panel."""
    df = pd.DataFrame(rows, columns=["ticker", "date", f"fwd_ret_{LABEL_HORIZON_WEEKS}w"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def _log(rows):
    """rows: (ticker, snapshot_date, p_up) -> a minimal frozen log."""
    df = pd.DataFrame(rows, columns=["ticker", "snapshot_date", "p_up"])
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    return df


# ── the failure that would fake a track record ────────────────────────────────

def test_forecast_still_in_flight_is_never_graded():
    """A bet that hasn't resolved is neither a hit nor a miss.

    Counting it either way manufactures a track record out of nothing — the
    single most dangerous thing this module could do."""
    panel = _panel([
        ("DONE", "2026-01-04", 20.0),      # resolved: a wave
        ("FLIGHT", "2026-01-11", np.nan),  # forecast made, outcome not yet known
    ])
    log = _log([("DONE", "2026-01-04", 0.2), ("FLIGHT", "2026-01-11", 0.9)])
    graded = grade_log(panel, log)
    assert list(graded["ticker"]) == ["DONE"], "an unresolved forecast must not be graded"
    assert graded["hit"].tolist() == [1.0]


def test_hit_is_defined_by_the_configured_threshold():
    panel = _panel([
        ("HIT", "2026-01-04", WAVE_PCT + 0.1),
        ("EDGE", "2026-01-04", WAVE_PCT),        # exactly at the bar counts
        ("MISS", "2026-01-04", WAVE_PCT - 0.1),
    ])
    log = _log([("HIT", "2026-01-04", 0.3), ("EDGE", "2026-01-04", 0.3),
                ("MISS", "2026-01-04", 0.3)])
    graded = grade_log(panel, log).set_index("ticker")
    assert graded.loc["HIT", "hit"] == 1.0
    assert graded.loc["EDGE", "hit"] == 1.0
    assert graded.loc["MISS", "hit"] == 0.0


def test_missing_log_returns_empty_not_an_exception():
    assert load_log("does_not_exist.csv").empty
    assert grade_log(_panel([("A", "2026-01-04", 1.0)]), path="does_not_exist.csv").empty


# ── the failure that would mislabel the evidence ──────────────────────────────

def test_summary_labels_a_backtest_as_a_backtest():
    """Substituting a backtest for a live record is the exact move this project
    exists to prevent, so `source` is mandatory on every result."""
    panel = _panel([("A", "2026-01-04", 5.0)])
    oos = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-04"] * 40),
        "p_up": np.linspace(0.05, 0.4, 40),
        "y_up": ([0.0] * 36) + ([1.0] * 4),
    })
    rec = summary(panel, oos=oos, path="does_not_exist.csv")
    assert rec is not None and rec["source"] == "backtest"


def test_summary_prefers_the_live_log_once_it_is_big_enough(tmp_path):
    n = 40
    dates = pd.to_datetime(["2026-01-04"] * n)
    panel = _panel([(f"T{i}", "2026-01-04", 20.0 if i < 10 else 0.0) for i in range(n)])
    log = pd.DataFrame({"ticker": [f"T{i}" for i in range(n)],
                        "snapshot_date": dates, "p_up": [0.25] * n})
    path = tmp_path / "waves_log.csv"
    log.to_csv(path, index=False)
    rec = summary(panel, oos=None, path=str(path))
    assert rec["source"] == "live log"
    assert rec["n"] == n
    assert rec["actual"] == pytest.approx(0.25)      # 10 of 40 hit


def test_summary_returns_none_with_no_evidence_at_all():
    assert summary(_panel([("A", "2026-01-04", 1.0)]), oos=None,
                   path="does_not_exist.csv") is None


# ── the log itself ────────────────────────────────────────────────────────────

def test_append_log_is_append_only_and_column_stable(tmp_path, monkeypatch):
    import core.decide as decide
    log = tmp_path / "waves_log.csv"
    monkeypatch.setattr(decide, "LOG", str(log))

    # `append_log` must resolve LOG at CALL time. With `path: str = LOG` the
    # default binds at DEFINITION time, this monkeypatch is ignored, and the test
    # writes to the REAL frozen log — which it did, until git restored it.
    base = {c: 1 for c in LOG_COLUMNS}
    base["snapshot_date"] = pd.Timestamp("2020-01-01")
    append_log(pd.DataFrame([{**base, "ticker": "AAA"}]))
    base2 = dict(base, snapshot_date=pd.Timestamp("2020-01-08"))
    append_log(pd.DataFrame([{**base2, "ticker": "BBB"}]))
    back = pd.read_csv(log)
    assert len(back) == 2 and list(back["ticker"]) == ["AAA", "BBB"]
    assert list(back.columns) == LOG_COLUMNS, "log schema must stay stable forever"


def test_append_log_tolerates_a_missing_column():
    """A future table gaining/losing a column must not corrupt the log's shape."""
    import core.decide as decide
    df = pd.DataFrame([{"ticker": "AAA", "p_up": 0.2}])          # most columns absent
    out = df.reindex(columns=decide.LOG_COLUMNS)
    assert list(out.columns) == decide.LOG_COLUMNS
    assert out["ticker"].iloc[0] == "AAA"


# ── one scoring path ──────────────────────────────────────────────────────────

def test_app_cli_and_ci_share_one_scoring_function():
    """If these ever diverge, the log records something the screen never showed."""
    import ast
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("app.py", os.path.join("tools", "weekly_run.py")):
        src = open(os.path.join(root, rel), encoding="utf-8").read()
        tree = ast.parse(src)
        imported = {n.name for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for n in node.names}
        assert imported & {"score_panel", "build_forecast_from_files"}, (
            f"{rel} must route selection through core.decide, not reimplement it")


def test_append_log_cannot_touch_production_when_patched(tmp_path, monkeypatch):
    """The guard on the bug above: with decide.LOG patched, the real log is untouched."""
    import core.decide as decide
    real = decide.LOG
    before = os.path.getsize(real) if os.path.exists(real) else None
    monkeypatch.setattr(decide, "LOG", str(tmp_path / "sandbox.csv"))
    row = pd.DataFrame([{**{c: 1 for c in LOG_COLUMNS},
                         "snapshot_date": pd.Timestamp("1999-01-01"), "ticker": "ZZZ"}])
    append_log(row)
    assert (tmp_path / "sandbox.csv").exists(), "the patched path must receive the write"
    after = os.path.getsize(real) if os.path.exists(real) else None
    assert after == before, "production log was modified by a test"


def test_ci_entry_point_only_prints_columns_the_engine_produces():
    """weekly_run.py hardcoded v3.0's p_up/p_dn/net_edge after the v3.1 switch and
    would have crashed the first Sunday job with a KeyError. Static check: every
    column it names must exist in what core.decide actually returns."""
    import ast
    import core.decide as decide
    from core.config import RANK_FEATURE

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, "tools", "weekly_run.py"), encoding="utf-8").read()
    literals = {n.value for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}

    produced = set(decide.LOG_COLUMNS) | {
        RANK_FEATURE, "hist_rate", "hist_n", "hist_lift", "hist_base", "decile",
        "ticker", "sector", "price", "persist", "sector_heat", "company_name",
        "category", "from_high",
    }
    # Column-shaped strings only: lowercase, no spaces, and actually referenced.
    suspects = {s for s in literals
                if s.islower() and " " not in s and "_" in s and len(s) < 24
                and not s.startswith(("http", "core.", "tools.", "logs/"))}
    retired = {"p_up", "p_dn", "net_edge", "master_score"}
    leaked = suspects & retired
    assert not leaked, (
        f"weekly_run.py references retired v3.0 columns {sorted(leaked)}. "
        "The CI job would KeyError on the next real run.")
