"""
WAVE 3.0 — locked configuration. THE single source of truth for every parameter.

Every value here is LOCKED by docs/PREREGISTRATION.md (2026-08-23). Changes are
allowed only at scheduled review windows, only with out-of-sample evidence from
the frozen forecast log, and only with a dated addendum in the pre-registration.
If you are editing this file outside a review window, you are the failure mode
this system was built to prevent.
"""

MODEL_VERSION = "3.1"
FIRST_REVIEW = "2027-02-21"          # 26 logged weeks after the first frozen forecast

# ── Data source ───────────────────────────────────────────────────────────────
# The public Drive folder holding Stocks_Weekly_*.csv. NOT a secret: the folder is
# already shared "Anyone with the link -> Viewer", so the URL protects nothing and
# hiding it in a repo variable only creates a step someone must remember. Verified
# 2026-08-23: resolves to 50 dated files, 2025-08-30 -> 2026-08-02.
# Override at runtime with the WAVE_DRIVE_FOLDER env var if the folder ever moves.
DRIVE_FOLDER_WEEKLY = "https://drive.google.com/drive/folders/1r9Y2E3_fOCLiBTBFFwu9KwG_AVopzsLq"
# Daily archive — execution testing only, NEVER training (ledger #56: half the market
# span, 96% label overlap).
DRIVE_FOLDER_DAILY = "https://drive.google.com/drive/folders/1B_TQWQW3Y-Y4jlVB3svdmMqsoPB_xd5S"
# Monthly archive — recorded for completeness, currently UNUSED. Its one genuine
# virtue is that monthly snapshots give near-NON-OVERLAPPING 4-week labels (weekly
# labels overlap 75%, daily 96%), which would make its t-stats honest without a
# haircut. But 11 files is 11 observations. Revisit at ~40 (≈2029).
DRIVE_FOLDER_MONTHLY = "https://drive.google.com/drive/folders/16R8jvFwf5GS1NOxVIwvjVkjuPN175E6t"

# ── Units ─────────────────────────────────────────────────────────────────────
CRORE = 1e7                          # ₹1 crore in rupees

# ── Wave definition (docs/PLAN.md §5) ─────────────────────────────────────────
WAVE_PCT = 15.0                      # a wave  = +15% over the label horizon
CRASH_PCT = -15.0                    # a crash = −15% over the label horizon
LABEL_HORIZON_WEEKS = 4

# How old the newest snapshot may be before freezing it is no longer a FORECAST.
# The weekly backup lands Sunday 21:00 IST and the job runs 23:00 IST, so a healthy
# run sees an age of 0. A stalled backup pipeline shows up as 7+, and freezing a
# week-old snapshot silently spends part of the label window before the forecast is
# even written — at 21 days (the observed Drive stall) 75% of the outcome is already
# determined, and the row is indistinguishable in the log from an honest one.
# 5 admits a mid-week manual dispatch and refuses a whole missed week.
MAX_SNAPSHOT_AGE_DAYS = 5

# ── Universe screen (tradeability, not alpha: where winners are BUYABLE) ──────
MIN_PRICE = 50.0                     # ₹ — below this, 1-rupee quantization dominates
MIN_MARKET_CAP = 500 * CRORE         # the Small Cap floor
MIN_TURNOVER = 1e7                   # ₹1Cr median 30d turnover

# ── Probability model (core/odds.py) ──────────────────────────────────────────
EMBARGO_DAYS = 29                    # label horizon + 1 day — the no-leakage wall
MIN_TRAIN_WEEKS = 26

# ── Portfolio (core/decide.py) ────────────────────────────────────────────────
# Mid + Small, NOT "all". Unrestricted, Large+Mega take 13 of 30 slots (43%) and
# drag the result from +15.18%/yr to +6.42%/yr — they rank high on range_pos because
# they are LESS volatile (a steady grind sits at the 95th percentile of a narrow
# range), which is a different event from a mid cap at the 95th of a wide one.
# Measured weakest in three independent tests; the 37-year literature predicts it.
UNIVERSE_CATEGORIES = ("Mid Cap", "Small Cap")
TOP_N = 30
MAX_PER_SECTOR = 3                   # THE SEATBELT — not tunable, whatever sector_heat says
HOLD_WEEKS = 8
TRAIL_STOP_PCT = 20.0                # tail insurance on DAILY closes (weekly lies by 22pp/yr)
COST_BPS = 57.6                      # realistic Indian round trip (STT+brokerage+impact)

# ── v3.1: rank by ONE measured column, odds COUNTED not fitted ────────────────
# The 13-feature logistic scored 1.07x lift; range_pos alone scored 1.36x
# (ledger #55). The model was subtracting performance, so it is demoted to the Lab.
RANK_FEATURE = "p_range_pos"
N_BINS = 10                          # deciles: ~4,500 rows/cell over the archive.
                                     # Finer bins are noise; 3-feature conditioning
                                     # would give ~45/cell.
