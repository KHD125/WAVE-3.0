"""
WAVE 3.0 core — the engine. Canonical pipeline order lives HERE, in one place,
exactly as PRISM's core.run_scoring_pipeline() pins its four steps:

    0. panel.build_panel()        honest data: forward returns joined on CALENDAR
                                  dates, delistings = -100% (counted, never dropped),
                                  corporate actions quarantined via 52w-level rescaling,
                                  universe screen FLAGGED (never deleted)
    1. scan.compute_features()    10 raw measurements -> within-week percentiles.
       WHY after panel: percentiles rank only `in_universe` rows, which panel defines.
    2. track.compute_track()      time axis (persist) + sector axis (heat/breadth).
       WHY after scan: both axes are built FROM p_range_pos, which scan creates.
    3. odds (walk-forward)        P(wave) / P(crash), 29-day label embargo — judged
       by calibration, nothing else. WHY after track: the locked feature set
       (ledger #51-52) includes persist + sector_heat + sector_breadth.
    4. decide                     the Sunday table + the append-only forecast log.
       ZERO new modelling — selection and freezing only.

The order is absolute. Reordering it recreates the class of bug that made the
legacy system's market_state filter structurally dead (it ran before the column
it filtered on existed).
"""

from .config import MODEL_VERSION  # noqa: F401  (the version tag rides with the package)


def run_feature_pipeline(panel):
    """Stages 1-2 in their locked order. Input: the panel from stage 0."""
    from .scan import compute_features
    from .track import compute_track
    return compute_track(compute_features(panel))
