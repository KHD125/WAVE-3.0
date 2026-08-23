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


def test_powershell_fallback_is_ascii_and_parses():
    """tools/weekly.ps1 did not PARSE, and nothing noticed.

    Windows PowerShell 5.1 reads a .ps1 as ANSI unless the file has a UTF-8 BOM.
    The script held em-dashes; under cp1252 the 0x94 byte decodes to a right
    double quote, which PowerShell honours as a string delimiter -- strings closed
    early, braces went unbalanced, the file failed to parse. As a scheduled task it
    would have done nothing every Sunday, silently, which is worse than no fallback
    at all because it looks like coverage.

    ASCII-only makes the encoding irrelevant. This test is the only thing standing
    between the script and the next well-meant em-dash.
    """
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "tools", "weekly.ps1")
    assert os.path.exists(path), "the Task Scheduler fallback is missing"
    raw = open(path, "rb").read()

    offenders = [(i + 1, line.decode("utf-8", "replace"))
                 for i, line in enumerate(raw.split(b"\n"))
                 if any(b > 127 for b in line)]
    assert not offenders, (
        "non-ASCII bytes in weekly.ps1 line(s) "
        f"{[n for n, _ in offenders]}: under cp1252 these can decode to quote "
        "characters and break the parse. Use plain ASCII.")

    # Balanced quotes and braces -- a cheap structural proxy for "it parses".
    text = raw.decode("ascii")
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    assert code.count('"') % 2 == 0, "unbalanced double quotes in weekly.ps1"
    assert code.count("{") == code.count("}"), "unbalanced braces in weekly.ps1"


def test_requirements_are_internally_consistent():
    """requirements.txt pinned streamlit~=1.54 beside pandas~=3.0, which CANNOT
    resolve: streamlit<=1.55 declares `pandas<3`. Streamlit Cloud's installer
    aborted with ResolutionImpossible before the app was ever built.

    Nothing caught it because nothing ever resolved the file. The dev venv had both
    installed side by side -- pip only WARNS when an upgrade breaks an existing
    pin, so the environment worked locally while being impossible to reproduce.
    This is `pip check` narrowed to our own pins, and it needs no network.

    SKIPS when the environment does not match requirements.txt, so a drifted dev
    venv reports honestly instead of raising a false alarm.
    """
    import os
    from importlib.metadata import PackageNotFoundError, distribution, distributions
    from packaging.requirements import Requirement

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lines = [l.split("#")[0].strip()
             for l in open(os.path.join(root, "requirements.txt"), encoding="utf-8")]
    pinned = {}
    for line in lines:
        if not line:
            continue
        req = Requirement(line)
        try:
            have = distribution(req.name).version
        except PackageNotFoundError:
            pytest.skip(f"{req.name} not installed; env does not match requirements.txt")
        if not req.specifier.contains(have, prereleases=True):
            pytest.skip(f"{req.name} {have} does not match the pin '{line}'; "
                        "resolve requirements.txt in a clean venv to test it")
        pinned[req.name.lower().replace("-", "_")] = have

    # Every installed package's own declared needs must admit the versions we pin.
    conflicts = []
    for dist in distributions():
        for raw in (dist.requires or []):
            dep = Requirement(raw)
            if dep.marker and not dep.marker.evaluate():
                continue                       # extras / platform-gated, not active
            key = dep.name.lower().replace("-", "_")
            if key in pinned and not dep.specifier.contains(pinned[key], prereleases=True):
                conflicts.append(
                    f"{dist.metadata['Name']} {dist.version} requires "
                    f"{dep.name}{dep.specifier}, but requirements.txt pins "
                    f"{dep.name}=={pinned[key]}")
    assert not conflicts, (
        "requirements.txt cannot be installed as written -- Streamlit Cloud will "
        "abort with ResolutionImpossible:\n  " + "\n  ".join(sorted(set(conflicts))))
