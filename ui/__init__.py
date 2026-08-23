"""WAVE 3.0 UI layer. One module per tab, mirroring PRISM's ui/ package.

Two laws carried over from PRISM (CLAUDE.md §5):
  * ui_tearsheet.py is STATELESS — no st.button/slider/session_state writes.
    app.py owns selection state; the tear sheet only renders what it is given.
  * ui_scanner.py is the deliberate STATEFUL counterpart — it OWNS the filter
    cascade. Do not "harmonize" the two.
"""
