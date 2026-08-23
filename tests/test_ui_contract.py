"""
Static contract tests for the UI layer — modelled on PRISM's
test_tearsheet_stateless_contract.py.

A documented invariant that isn't pinned by a test drifts. PRISM learned this
when its stateless-UI rule silently regressed; these tests exist so WAVE's
architecture can't rot the same way.
"""

import ast
import os

import pytest

UI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")
APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

# Widgets that write st.session_state. Banned in the tear sheet.
STATEFUL_WIDGETS = {
    "button", "slider", "select_slider", "selectbox", "multiselect", "text_input",
    "number_input", "checkbox", "radio", "file_uploader", "date_input", "toggle",
}


def _tree(path):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


def _st_calls(tree):
    """Every `<anything>.<name>(...)` call in the module.

    Deliberately receiver-agnostic: Streamlit widgets are called on `st` AND on
    columns/containers (`c1.multiselect(...)`). Matching only `st.` made the
    scanner look stateless and would have waved a real tear-sheet violation
    through — the exact blind spot this contract exists to prevent."""
    return [n.func.attr for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]


def test_tearsheet_is_stateless():
    """ui_tearsheet must never own state — app.py owns selection (PRISM's rule)."""
    calls = set(_st_calls(_tree(os.path.join(UI, "ui_tearsheet.py"))))
    offenders = calls & STATEFUL_WIDGETS
    assert not offenders, (
        f"ui_tearsheet.py uses stateful widgets {sorted(offenders)}. It renders what it "
        "is given; app.py owns selection. The stateful counterpart is ui_scanner.py.")


def test_tearsheet_never_touches_session_state():
    """AST, not grep: the module docstring names session_state to explain the ban."""
    tree = _tree(os.path.join(UI, "ui_tearsheet.py"))
    touches = [n for n in ast.walk(tree)
               if isinstance(n, ast.Attribute) and n.attr == "session_state"]
    assert not touches, "ui_tearsheet.py must not read or write session_state"


def test_scanner_is_the_stateful_counterpart():
    """The split is deliberate: proving the scanner DOES own widgets stops a
    well-meaning future edit from 'harmonizing' the two files."""
    calls = set(_st_calls(_tree(os.path.join(UI, "ui_scanner.py"))))
    assert calls & STATEFUL_WIDGETS, "ui_scanner.py is supposed to own the filter cascade"


def test_app_is_thin():
    """app.py owns navigation and state — not computation."""
    tree = _tree(APP)
    banned = {"fit_predict_one", "walk_forward", "compute_features", "compute_track",
              "calibration_table", "brier_score"}
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    leaked = (called & banned) - {"fit_predict_one"}   # the one orchestration call it may make
    assert not leaked, f"app.py is computing {sorted(leaked)} — that belongs in core/"


@pytest.mark.parametrize("module", ["ui_summary", "ui_scanner", "ui_tearsheet",
                                    "ui_pulse", "ui_backtest", "ui_reference"])
def test_every_tab_module_exposes_render(module):
    tree = _tree(os.path.join(UI, f"{module}.py"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "render" in names, f"{module}.py must expose render(ctx)"


def test_core_never_imports_streamlit():
    """The engine must be usable headless — from a cron job, a notebook, a test.
    A core module that imports streamlit has fused the calculation to its display."""
    offenders = []
    for fn in os.listdir(CORE):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(CORE, fn), encoding="utf-8").read()
        if "import streamlit" in src:
            offenders.append(fn)
    assert not offenders, f"core modules import streamlit: {offenders}"


def test_locked_parameters_live_only_in_config():
    """Magic numbers in core/ are how a locked design quietly drifts. Every
    threshold belongs in config.py, imported by name."""
    src = open(os.path.join(CORE, "decide.py"), encoding="utf-8").read()
    for literal in ("= 30", "= 3 ", '= "Mid Cap"'):
        assert literal not in src, (
            f"decide.py hardcodes {literal!r} — import it from core.config instead")
