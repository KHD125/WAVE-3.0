"""ui.ui_reference — Tab 6. The rulebook: glossary, laws, pre-registration."""

from __future__ import annotations

import os

import streamlit as st

from core.config import FIRST_REVIEW, MODEL_VERSION
from ui.ui_reference_data import GLOSSARY

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOCS = os.path.join(_ROOT, "docs")


def _doc(name: str) -> str:
    p = os.path.join(_DOCS, name)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else f"_{name} not found._"


def render(ctx: dict) -> None:
    st.subheader("Reference")
    st.caption(f"WAVE {MODEL_VERSION} · every term defined by what it IS **and** what it "
               f"MEASURED · first review {FIRST_REVIEW}")

    t1, t2, t3 = st.tabs(["📖 Glossary", "⚖️ The laws", "📝 Pre-registration"])
    with t1:
        for section, entries in GLOSSARY.items():
            st.markdown(f"#### {section}")
            for term, text in entries.items():
                with st.expander(term):
                    st.markdown(text)
    with t2:
        st.markdown(_doc("PLAN.md"))
    with t3:
        st.markdown(_doc("PREREGISTRATION.md"))
