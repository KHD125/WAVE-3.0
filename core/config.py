"""
WAVE 3.0 — locked configuration. THE single source of truth for every parameter.

Every value here is LOCKED by docs/PREREGISTRATION.md (2026-08-23). Changes are
allowed only at scheduled review windows, only with out-of-sample evidence from
the frozen forecast log, and only with a dated addendum in the pre-registration.
If you are editing this file outside a review window, you are the failure mode
this system was built to prevent.
"""

MODEL_VERSION = "3.0"
FIRST_REVIEW = "2027-02-21"          # 26 logged weeks after the first frozen forecast

# ── Units ─────────────────────────────────────────────────────────────────────
CRORE = 1e7                          # ₹1 crore in rupees

# ── Wave definition (docs/PLAN.md §5) ─────────────────────────────────────────
WAVE_PCT = 15.0                      # a wave  = +15% over the label horizon
CRASH_PCT = -15.0                    # a crash = −15% over the label horizon
LABEL_HORIZON_WEEKS = 4

# ── Universe screen (tradeability, not alpha: where winners are BUYABLE) ──────
MIN_PRICE = 50.0                     # ₹ — below this, 1-rupee quantization dominates
MIN_MARKET_CAP = 500 * CRORE         # the Small Cap floor
MIN_TURNOVER = 1e7                   # ₹1Cr median 30d turnover

# ── Probability model (core/odds.py) ──────────────────────────────────────────
EMBARGO_DAYS = 29                    # label horizon + 1 day — the no-leakage wall
MIN_TRAIN_WEEKS = 26

# ── Portfolio (core/decide.py) ────────────────────────────────────────────────
UNIVERSE_CATEGORY = "Mid Cap"        # ~92% of its top-100 winners are investable
TOP_N = 30
MAX_PER_SECTOR = 3                   # THE SEATBELT — not tunable, whatever sector_heat says
HOLD_WEEKS = 8
TRAIL_STOP_PCT = 20.0                # tail insurance on DAILY closes (weekly lies by 22pp/yr)
COST_BPS = 57.6                      # realistic Indian round trip (STT+brokerage+impact)
