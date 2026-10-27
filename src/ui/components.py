"""Piezas de interfaz reutilizadas por todas las páginas de Streamlit."""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.ingestion.fit_loader import load_fit, prepare_records
from src.processing.metrics import format_number as fmt
from src.visualization.theme import ACCENT, BORDER, CARD, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY

ROOT = Path(__file__).resolve().parents[2]
FIT_FOLDER = ROOT / "data" / "raw" / "fit"

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def format_date(value: datetime | None, with_time: bool = False) -> str:
    if value is None:
        return "Fecha desconocida"
    text = f"{value.day:02d} {MONTHS[value.month - 1]} {value.year}"
    return f"{text} · {value:%H:%M}" if with_time else text


# ---------- Carga de datos (con caché) ----------

def list_fit_files() -> list[Path]:
    FIT_FOLDER.mkdir(parents=True, exist_ok=True)
    return sorted(FIT_FOLDER.glob("*.fit"))


@st.cache_data(show_spinner="Leyendo archivo FIT...")
def _load_from_path(path: str, modified: float) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    raw, session = load_fit(path)
    return raw, prepare_records(raw), session


@st.cache_data(show_spinner="Leyendo archivo FIT...")
def load_from_bytes(data: bytes) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    raw, session = load_fit(data)
    return raw, prepare_records(raw), session


def load_from_path(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    # La fecha de modificación forma parte de la clave de caché:
    # si el archivo cambia, se vuelve a leer.
    return _load_from_path(str(path), path.stat().st_mtime)


# ---------- Estilos y componentes visuales ----------

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stMarkdown, .stText {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
.block-container {{ padding-top: 3.2rem; max-width: 1400px; }}

.hero {{
  background: linear-gradient(120deg, rgba(217,89,38,0.22) 0%, rgba(57,135,229,0.12) 60%, rgba(0,0,0,0) 100%), {CARD};
  border: 1px solid {BORDER}; border-radius: 18px; padding: 1.6rem 2rem; margin-bottom: 1.4rem;
}}
.hero .eyebrow {{ color: {ACCENT}; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; font-size: .78rem; }}
.hero h1 {{ color: {TEXT_PRIMARY}; font-size: 2.1rem; font-weight: 800; margin: .2rem 0 .3rem 0; padding: 0; }}
.hero .sub {{ color: {TEXT_SECONDARY}; font-size: .98rem; }}

.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .9rem; margin-bottom: 1rem; }}
.kpi {{
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; padding: 1rem 1.1rem;
  position: relative; overflow: hidden; transition: transform .15s ease, border-color .15s ease;
}}
.kpi:hover {{ transform: translateY(-2px); border-color: {ACCENT}; }}
.kpi::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--kpi-color, {ACCENT}); }}
.kpi .label {{ color: {TEXT_MUTED}; font-size: .78rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }}
.kpi .value {{ color: {TEXT_PRIMARY}; font-size: 1.75rem; font-weight: 700; line-height: 1.25; margin-top: .25rem; }}
.kpi .unit {{ color: {TEXT_SECONDARY}; font-size: .95rem; font-weight: 500; margin-left: .2rem; }}
.kpi .hint {{ color: {TEXT_MUTED}; font-size: .78rem; margin-top: .15rem; }}


.section-title {{ color: {TEXT_PRIMARY}; font-size: 1.15rem; font-weight: 700; margin: 1rem 0 .2rem 0; }}
.caption {{ color: {TEXT_MUTED}; font-size: .85rem; margin-bottom: .6rem; }}

.stTabs [data-baseweb="tab-list"] {{ gap: .4rem; }}
.stTabs [data-baseweb="tab"] {{ background: {CARD}; border-radius: 10px 10px 0 0; padding: .5rem 1rem; }}
[data-testid="stSidebar"] {{ border-right: 1px solid {BORDER}; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{html.escape(eyebrow)}</div>'
        f"<h1>{html.escape(title)}</h1><div class=\"sub\">{html.escape(subtitle)}</div></div>",
        unsafe_allow_html=True,
    )


def kpi_cards(cards: list[dict]) -> None:
    """Cada tarjeta: {label, value, unit?, hint?, color?}."""
    items = []
    for c in cards:
        unit = f'<span class="unit">{html.escape(c["unit"])}</span>' if c.get("unit") and c["value"] != "—" else ""
        hint = f'<div class="hint">{html.escape(c["hint"])}</div>' if c.get("hint") else ""
        color = f' style="--kpi-color:{c["color"]}"' if c.get("color") else ""
        items.append(
            f'<div class="kpi"{color}><div class="label">{html.escape(c["label"])}</div>'
            f'<div class="value">{html.escape(c["value"])}{unit}</div>{hint}</div>'
        )
    st.markdown(f'<div class="kpi-grid">{"".join(items)}</div>', unsafe_allow_html=True)


def section(title: str, caption: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="caption">{html.escape(caption)}</div>', unsafe_allow_html=True)
