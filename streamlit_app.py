"""Streamlit Cloud entry point.

A deployed checkout is clean: storage/ is gitignored, so neither the SQLite
database nor the vector index exists on first boot. Both are built here before
the UI loads, otherwise the app deploys with no doctors, no slots and no
knowledge base.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

DB_PATH = ROOT / "storage" / "clinic.db"


@st.cache_resource(show_spinner="Preparing the clinic database…")
def _bootstrap() -> bool:
    """Seed the database once per container. Cached so it runs only on cold start."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        from scripts.seed_database import main as seed
        seed()
    return True


_bootstrap()

from app.ui.streamlit_app import main  # noqa: E402  (must follow bootstrap)

main()