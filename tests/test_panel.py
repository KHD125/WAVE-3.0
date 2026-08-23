"""
Contract tests for alpha.panel.

Each test pins one HARD RULE from the module docstring. These are the rules that,
when broken, produce a backtest that looks excellent and is wrong — the failure
mode is silent, so it has to be pinned rather than reviewed.
"""

import numpy as np
import pandas as pd
import pytest

from core.panel import (
    CRORE,
    add_forward_returns,
    apply_universe_screen,
    parse_date_from_filename,
    parse_indian_numeric,
)


def _panel(rows):
    """rows: (ticker, 'YYYY-MM-DD', price) -> a minimal panel."""
    df = pd.DataFrame(rows, columns=["ticker", "date", "price"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


# ── Indian numeric parsing ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("₹1,091", 1091.0),      # rupee + thousands separator
        ("₹745", 745.0),
        ("46.36%", 46.36),            # percent stays in PERCENT units
        ("-6.79%", -6.79),
        ("725866", 725866.0),
        ("₹12,987 Cr", 12987.0), # magnitude suffix stripped, not parsed as digits
    ],
)
def test_parse_indian_numeric_formats(raw, expected):
    assert parse_indian_numeric(pd.Series([raw])).iloc[0] == pytest.approx(expected)


def test_parse_indian_numeric_returns_nan_not_zero():
    """Missing data must stay distinguishable from a genuine zero."""
    out = parse_indian_numeric(pd.Series(["", "-", None, "n/a"]))
    assert out.isna().all(), "unparseable input must be NaN, never a 0 sentinel"


def test_parse_indian_numeric_passes_through_numeric():
    out = parse_indian_numeric(pd.Series([1.5, 2.5]))
    assert out.tolist() == [1.5, 2.5]


def test_market_cap_scale_converts_crore_to_rupees():
    assert parse_indian_numeric(pd.Series(["₹1 Cr"]), scale=CRORE).iloc[0] == pytest.approx(CRORE)


def test_parse_date_from_filename():
    assert parse_date_from_filename("Stocks_Weekly_2026-08-16_Aug_2026.csv") == pd.Timestamp("2026-08-16")
    assert parse_date_from_filename("no_date_here.csv") is None


# ── THE bug this module exists to prevent ─────────────────────────────────────

def test_forward_return_joins_on_date_not_row_offset():
    """
    GAP has no row for week 2. A `groupby(ticker).shift(-1)` would pair its
    week-1 price with its week-3 price and label a 2-week return as 1-week.
    The date join must leave that observation missing instead.
    """
    panel = _panel([
        ("FULL", "2026-01-05", 100.0),
        ("FULL", "2026-01-12", 110.0),
        ("FULL", "2026-01-19", 121.0),
        ("GAP",  "2026-01-05", 100.0),
        # GAP absent on 2026-01-12
        ("GAP",  "2026-01-19", 200.0),
    ])
    out, _ = add_forward_returns(panel, horizons_weeks=(1,), delisting_return_pct=np.nan)

    full = out[(out["ticker"] == "FULL") & (out["date"] == "2026-01-05")]["fwd_ret_1w"].iloc[0]
    assert full == pytest.approx(10.0)

    gap = out[(out["ticker"] == "GAP") & (out["date"] == "2026-01-05")]["fwd_ret_1w"].iloc[0]
    assert np.isnan(gap), f"row-offset leakage: got {gap}, a 2-week return mislabelled as 1-week"


def test_delisting_is_recorded_as_a_loss_not_dropped():
    """
    A ticker that vanishes is the backtest's most important observation. If it
    becomes NaN and is filtered out, the strategy silently deletes its own losses.
    """
    panel = _panel([
        ("ALIVE", "2026-01-05", 100.0),
        ("ALIVE", "2026-01-12", 105.0),
        ("DEAD",  "2026-01-05", 100.0),
        # DEAD never appears again
    ])
    out, report = add_forward_returns(panel, horizons_weeks=(1,))

    dead = out[out["ticker"] == "DEAD"]["fwd_ret_1w"].iloc[0]
    assert dead == pytest.approx(-100.0)
    assert report.delistings == 1
    assert len(out) == 3, "no row may be dropped by forward-return construction"


def test_end_of_sample_is_nan_not_a_delisting():
    """Past the last snapshot the outcome is unknowable — that is NOT a loss."""
    panel = _panel([("A", "2026-01-05", 100.0), ("A", "2026-01-12", 105.0)])
    out, report = add_forward_returns(panel, horizons_weeks=(1,))

    last = out[out["date"] == "2026-01-12"]["fwd_ret_1w"].iloc[0]
    assert np.isnan(last), "sample-end must be NaN, never -100%"
    assert report.delistings == 0


def test_zero_and_missing_base_price_never_divide():
    panel = _panel([
        ("ZERO", "2026-01-05", 0.0),
        ("ZERO", "2026-01-12", 50.0),
        ("NULL", "2026-01-05", np.nan),
        ("NULL", "2026-01-12", 50.0),
    ])
    out, _ = add_forward_returns(panel, horizons_weeks=(1,))
    vals = out[out["date"] == "2026-01-05"]["fwd_ret_1w"]
    assert vals.isna().all(), "a zero/NaN base price must never produce a return"
    assert not np.isinf(out["fwd_ret_1w"].to_numpy(dtype=float)).any()


# ── Corporate actions ─────────────────────────────────────────────────────────

def test_split_is_flagged_and_a_real_crash_is_not():
    """
    A 1:5 split shows as -80% and must be quarantined. A -60% collapse is a real
    loss and must survive — discarding it would be the survivorship bug again,
    wearing a different hat.
    """
    panel = _panel([
        ("SPLIT", "2026-01-05", 500.0),
        ("SPLIT", "2026-01-12", 100.0),   # 1:5 — vendor rescales the levels too
        ("CRASH", "2026-01-05", 100.0),
        ("CRASH", "2026-01-12", 40.0),    # -60% real loss — 52w high does NOT move
    ])
    # The discriminator: BOTH 52w levels rescale on a split, neither on a crash.
    # Note -60% has ratio 0.4, inverse 2.5 — a "common split ratio". Price alone
    # would misclassify this real loss; the levels are what separate them.
    # Keyed by (ticker, date) on purpose — _panel() sorts, so a positional list
    # silently assigns SPLIT's levels to CRASH.
    levels = {
        ("SPLIT", "2026-01-05"): (600.0, 400.0),   # split rescales both...
        ("SPLIT", "2026-01-12"): (120.0, 80.0),    # ...by the same 0.2
        ("CRASH", "2026-01-05"): (150.0, 90.0),    # crash leaves the high alone
        ("CRASH", "2026-01-12"): (150.0, 40.0),    # only the low resets
    }
    key = list(zip(panel["ticker"], panel["date"].dt.strftime("%Y-%m-%d")))
    panel["high_52w"] = [levels[k][0] for k in key]
    panel["low_52w"] = [levels[k][1] for k in key]
    out, report = add_forward_returns(panel, horizons_weeks=(1,))
    first = out[out["date"] == "2026-01-05"].set_index("ticker")

    assert bool(first.loc["SPLIT", "is_corporate_action"]) is True
    assert bool(first.loc["CRASH", "is_corporate_action"]) is False
    assert bool(first.loc["CRASH", "is_suspect_move"]) is True
    assert report.corporate_actions == 1


# ── Universe screen ───────────────────────────────────────────────────────────

def test_universe_screen_flags_and_never_deletes():
    panel = _panel([("BIG", "2026-01-05", 1000.0), ("PENNY", "2026-01-05", 5.0)])
    panel["volume_30d"] = [1e6, 1e6]
    panel["market_cap"] = [5000 * CRORE, 1 * CRORE]

    out = apply_universe_screen(panel)
    assert len(out) == len(panel), "the screen must flag, never drop"
    flags = out.set_index("ticker")["in_universe"]
    assert bool(flags["BIG"]) is True
    assert bool(flags["PENNY"]) is False, "sub-floor price must fail the screen"


def test_universe_screen_excludes_missing_data_rather_than_assuming():
    """No market cap is not the same as a big market cap."""
    panel = _panel([("UNKNOWN", "2026-01-05", 1000.0)])
    panel["volume_30d"] = [1e6]
    panel["market_cap"] = [np.nan]
    assert not apply_universe_screen(panel)["in_universe"].iloc[0]


# ── Report ────────────────────────────────────────────────────────────────────

def test_report_counts_are_populated():
    """Silence is how bias hides — the report must always carry the numbers."""
    panel = _panel([
        ("A", "2026-01-05", 100.0),
        ("A", "2026-01-12", 110.0),
        ("B", "2026-01-05", 100.0),
    ])
    _, report = add_forward_returns(panel, horizons_weeks=(1,))
    assert report.n_rows == 3
    assert report.n_tickers == 2
    assert report.delistings == 1
    assert 0.0 <= report.coverage[1] <= 100.0
    assert "delistings" in report.render()


# ── Drive listing: the folder page caps at ~50 and lies about it ──────────────

def test_folder_listing_is_not_capped_by_the_50_item_page():
    """The /drive/folders/ page embeds only the first ~50 entries; the rest load on
    scroll. A scraper therefore sees a truncated folder and CANNOT TELL -- there is
    no error, just a shorter list whose newest files are missing.

    That cost a real misdiagnosis: a folder holding 53 weekly snapshots reported 50,
    the three NEWEST were the ones dropped, and the conclusion drawn was that the
    upstream backup had stalled three weeks earlier. Nothing had stalled. A silent
    cap that presents as stale data is worse than a crash, because it gets believed.

    Both listings are read and unioned by file id, so neither blind spot can hide a
    week.
    """
    from core.sources import _list_folder

    class _Resp:
        def __init__(self, text): self.text = text

    class _Session:
        def __init__(self, embed): self._embed = embed
        def get(self, url, timeout=None): return _Resp(self._embed)

    # embeddedfolderview: the full 53. Entry blocks in DOM order.
    embed = "".join(
        f'<div class="flip-entry"><a href="/file/d/{"i%02d" % i}xxxxxxxxxxxxxxxxxxxx/view">'
        f'</a><div class="flip-entry-title">Stocks_Weekly_wk{i:02d}.csv</div></div>'
        for i in range(53))
    # folder page: only the first 50, exactly as Drive serves it.
    page = "".join(f'["1{"p%02d" % i}xxxxxxxxxx","Stocks_Weekly_wk{i:02d}.csv"]'
                   for i in range(50))

    out = _list_folder(_Session(embed), "KEY", page)
    names = {n for _, n in out}
    assert len(names) == 53, f"listing capped at {len(names)} -- the newest weeks are gone"
    assert "Stocks_Weekly_wk52.csv" in names, "the NEWEST file is the one a cap drops"

    # The union must survive the embed endpoint failing entirely.
    class _Dead:
        def get(self, url, timeout=None): raise OSError("no network")
    fallback = _list_folder(_Dead(), "KEY", page)
    assert len(fallback) == 50, "must still fall back to the folder page"

    # ...and survive the folder page being unparseable.
    only_embed = _list_folder(_Session(embed), "KEY", "<html>nothing here</html>")
    assert len(only_embed) == 53
