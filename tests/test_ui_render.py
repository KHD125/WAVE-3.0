"""
Render tests — the gap that let a live app crash.

The static contract tests (test_ui_contract.py) verified the ARCHITECTURE and
passed 37/37 while the deployed app was throwing ImportError on every Tear Sheet
view. They cannot catch a missing runtime dependency, because they never render.

Two guards, cheapest first:
  1. a static ban on pandas Styler methods that need matplotlib
  2. a real in-process render via Streamlit's AppTest (PRISM's approach)
"""

import ast
import glob
import os
import re

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(_ROOT, "ui")
ARCHIVE = os.path.join(_ROOT, "Alpha Resources", "Weekly", "Stocks_Backups Weekly")

# Styler methods that silently require matplotlib. Absent on a lean deploy, they
# raise ImportError at RENDER time — long after every static check has gone green.
MATPLOTLIB_STYLER_METHODS = ("background_gradient", "text_gradient", "bar(")


def test_ui_never_uses_matplotlib_backed_stylers():
    """Use st.column_config.ProgressColumn instead — native, no dependency."""
    offenders = []
    for path in glob.glob(os.path.join(UI, "*.py")):
        src = open(path, encoding="utf-8").read()
        # ignore the explanatory comments that name the banned method
        code = "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))
        for method in MATPLOTLIB_STYLER_METHODS:
            if f".{method}" in code:
                offenders.append(f"{os.path.basename(path)} -> .{method}")
    assert not offenders, (
        "matplotlib-backed Styler methods found: " + ", ".join(offenders) +
        ". These crash on a deploy without matplotlib. Use "
        "st.column_config.ProgressColumn / NumberColumn instead.")


def test_requirements_covers_every_third_party_import():
    """Anything imported by core/ or ui/ must be declared, or the cloud lacks it."""
    req = open(os.path.join(_ROOT, "requirements.txt"), encoding="utf-8").read().lower()
    stdlib_ok = {"os", "sys", "io", "re", "glob", "ast", "math", "json", "typing",
                 "datetime", "dataclasses", "functools", "itertools", "logging",
                 "warnings", "collections", "__future__", "core", "ui", "tools"}
    # pip name != import name
    PIP_NAME = {"sklearn": "scikit-learn"}
    missing = set()
    for folder in ("core", "ui"):
        for path in glob.glob(os.path.join(_ROOT, folder, "*.py")):
            # AST, never a line regex: `\s*from\s+(\w+)` happily matches prose in
            # a docstring ("...ported from Alpha Trajectory...") and reports a
            # sentence as a missing dependency.
            tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    pkgs = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:          # `from .config import ...` is internal
                        continue
                    pkgs = [(node.module or "").split(".")[0]]
                else:
                    continue
                for pkg in pkgs:
                    if not pkg or pkg in stdlib_ok:
                        continue
                    if PIP_NAME.get(pkg, pkg).lower() not in req:
                        missing.add(pkg)
    assert not missing, f"imported but not in requirements.txt: {sorted(missing)}"


@pytest.mark.skipif(not os.path.isdir(ARCHIVE), reason="local archive not present")
def test_app_renders_every_tab_without_exception():
    """The test that would have caught the matplotlib crash.

    AppTest executes the real script in-process. Streamlit evaluates the body of
    EVERY st.tabs() branch on a run, so one render exercises all six tabs —
    including the Tear Sheet's feature table that took production down.
    """
    from streamlit.testing.v1 import AppTest

    paths = sorted(glob.glob(os.path.join(ARCHIVE, "*.csv")))[-12:]   # 12 weeks is enough
    files = [(os.path.basename(p), open(p, "rb").read()) for p in paths]

    at = AppTest.from_file(os.path.join(_ROOT, "app.py"), default_timeout=300)
    at.session_state["files"] = files
    at.run()

    assert not at.exception, (
        "app raised while rendering: "
        + "; ".join(str(e.value) for e in at.exception))
