"""
ui.ui_reference_data — the glossary content, separated from its rendering
(PRISM convention: ui_reference.py renders, ui_reference_data.py holds the words).

Every entry states what the thing IS and what it MEASURED. A definition without
its measurement is how "breakout_score: probability of price breakout" survived
for years describing a number nobody ever checked.
"""

GLOSSARY = {
    "The signal": {
        "range_pos": (
            "(price − 52w low) / (52w high − 52w low). Where the stock sits inside its own "
            "yearly range. **The one factor that survived the audit** — IC ≈ 0.076 at 8 weeks, "
            "stable across four different universe screens. Independently confirmed as the best "
            "of its family by a 37-year, nine-universe study (Informed Momentum Co., 2026). "
            "It works partly because dividing by the range divides by volatility, so it is a "
            "z-score with a built-in low-volatility tilt."),
        "persist": (
            "Consecutive weeks the stock has held the top tercile of range_pos. Alpha "
            "Trajectory's core thesis, finally measured (ledger #51): real, but 0.81 correlated "
            "with range_pos — the same factor wearing a time costume. Kept as one input, not "
            "as a second pillar."),
        "sector_heat / sector_breadth": (
            "The sector's average range_pos percentile, and the share of its members in the top "
            "tercile. **The best orthogonal find of the project** (ledger #52): IC +0.098 at 8 "
            "weeks with only 0.36 overlap with range_pos. Industry momentum, documented since "
            "Moskowitz–Grinblatt (1999)."),
    },
    "The odds": {
        "P(wave)": (
            "Modelled probability the stock gains ≥ +15% over the next 4 weeks. Produced by "
            "logistic regression on 13 percentile features, fitted **walk-forward** — the "
            "forecast for any week comes from a model that never saw that week, nor any week "
            "whose 4-week label overlaps it (29-day embargo)."),
        "P(crash)": "Same machinery, for ≤ −15% over 4 weeks.",
        "Net edge": (
            "P(wave) − P(crash). The ranking key. It exists because the audit found that every "
            "raw signal detects *movement*, not *direction* — future losers scored higher than "
            "future gainers on 1-week and 1-month returns. Subtracting the downside is the only "
            "honest way to read an upside number."),
        "Calibration": (
            "Whether a stated probability happens that often. When the model says 30%, does it "
            "occur ~30% of the time? **This is the only standard that matters** — a ranking can "
            "hide its failures, a probability cannot. Bar: within ±5pp per decile."),
        "Brier score": (
            "Mean squared error of stated probability vs outcome. 0 = oracle; always predicting "
            "the base rate scores p·(1−p). Supplements the calibration table, never replaces it "
            "— Brier blends calibration and discrimination into one number."),
    },
    "The guardrails": {
        "Universe screen": (
            "Price ≥ ₹50, market cap ≥ ₹500Cr, 30-day turnover ≥ ₹1Cr, Mid Cap. Tradeability, "
            "not alpha: ~92% of Mid Cap's top-100 winners are investable, versus barely half in "
            "Small Cap. Small caps' higher apparent IC largely lives in stocks you cannot buy."),
        "3 per sector": (
            "**The seatbelt.** Loosening it raises backtested alpha monotonically (+1.5%/yr at "
            "2/sector → +11.7%/yr uncapped) because it becomes a sector bet — which is also the "
            "trade that produces India's −70%, 65-month-recovery momentum crashes. Never tuned."),
        "57.6 bps": (
            "Assumed round-trip cost — brokerage, STT, stamp duty, exchange fees, GST, impact. "
            "The legacy system's headline strategy showed +0.86%/week; measured with costs it "
            "was +0.007%/week. Its entire gross edge was friction."),
        "−20% trailing stop": (
            "Tail insurance, on DAILY closes. Weekly closes overstate stop performance by up to "
            "22 percentage points a year, because a weekly bar hides the mid-week plunge that "
            "would really have triggered it. Wide, not tight: tight stops cost heavily in trends."),
        "The test counter": (
            "At N tests on one dataset, pure noise produces max|t| ≈ √(2·ln N). After ~50 tests "
            "that bar is 2.2–2.7, and the project's best result was 1.45. The counter exists so "
            "exploration stays honest rather than forbidden."),
    },
    "What was deleted, and why": {
        "42 patterns": (
            "PHOENIX RISING, ATOMIC DECAY MOMENTUM, INSTITUTIONAL TSUNAMI and 39 others. "
            "Measured against forward returns: **not one cleared |t| = 2.0**. Fourteen were "
            "effectively dead; five never fired once in 44 weeks. The five most heavily weighted "
            "were the five deadest."),
        "DNA scorers": (
            "Five cap-tier scorers, ~125 hand-tuned thresholds fitted to 28 weekly snapshots and "
            "then backtested on the same 28. Removed entirely."),
        "master_score": (
            "The legacy composite of six component scores. Measured IC ≈ −0.019 at one week; it "
            "adds nothing over the single raw range_pos column."),
    },
}
