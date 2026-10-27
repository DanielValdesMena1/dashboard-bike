"""Punto de entrada: `streamlit run app/streamlit_app.py`."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.ui.components import inject_css

st.set_page_config(page_title="Ride Analytics", page_icon="🚴", layout="wide")
inject_css()

VIEWS = Path(__file__).parent / "views"
page = st.navigation([
    st.Page(VIEWS / "actividad.py", title="Actividad", icon="🚴", default=True),
    st.Page(VIEWS / "resumen.py", title="Historial", icon="📊"),
])
page.run()
