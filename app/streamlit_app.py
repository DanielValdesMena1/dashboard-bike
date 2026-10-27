"""Punto de entrada: `streamlit run app/streamlit_app.py`."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.ui.components import inject_css
from src.ui.garmin_panel import auto_sync, get_account, sidebar_panel

st.set_page_config(page_title="Ride Analytics", page_icon="🚴", layout="wide")
inject_css()

# Garmin va antes que las páginas: así ven las actividades recién sincronizadas,
# y el panel se muestra aunque una página se detenga por no tener datos.
with st.sidebar:
    st.markdown("## 🚴 Ride Analytics")
    st.caption("Análisis de actividades de ciclismo a partir de archivos FIT de Garmin.")

garmin = get_account()
auto_sync(garmin)
sidebar_panel(garmin)

VIEWS = Path(__file__).parent / "views"
page = st.navigation([
    st.Page(VIEWS / "actividad.py", title="Actividad", icon="🚴", default=True),
    st.Page(VIEWS / "resumen.py", title="Historial", icon="📊"),
])
page.run()
