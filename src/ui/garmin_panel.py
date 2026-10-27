"""Conexión con Garmin Connect y sincronización automática desde la interfaz."""
from __future__ import annotations

import time

import streamlit as st

from src.ingestion.garmin_sync import SYNC_START, GarminAccount, read_state, sync_activities
from src.ui.components import format_date

AUTO_SYNC_EVERY_S = 15 * 60  # Al abrir el dashboard se sincroniza si pasaron más de 15 min


def get_account() -> GarminAccount:
    # Una cuenta por sesión del navegador: conserva el login a medias mientras se espera el MFA
    if "garmin_account" not in st.session_state:
        st.session_state["garmin_account"] = GarminAccount()
    return st.session_state["garmin_account"]


def _run_sync(account: GarminAccount) -> None:
    with st.spinner("Sincronizando actividades de Garmin Connect..."):
        try:
            result = sync_activities(account.api())
        except Exception as exc:
            st.session_state["garmin_synced"] = True
            st.toast(f"No se pudo iniciar sesión en Garmin: {exc}", icon="⚠️")
            return
    st.session_state["garmin_synced"] = True
    if result.error:
        st.toast(result.error, icon="⚠️")
    elif result.new:
        st.toast(f"{len(result.new)} actividad(es) nueva(s) desde Garmin", icon="🚴")


def auto_sync(account: GarminAccount) -> None:
    """Sincroniza una vez por sesión si la última sincronización es antigua."""
    if not account.is_connected or st.session_state.get("garmin_synced"):
        return
    if time.time() - read_state().get("last_sync", 0) > AUTO_SYNC_EVERY_S:
        _run_sync(account)
    else:
        st.session_state["garmin_synced"] = True


def _ago(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 1:
        return "hace un momento"
    if minutes < 60:
        return f"hace {minutes} min"
    hours = minutes // 60
    return f"hace {hours} h" if hours < 24 else f"hace {hours // 24} d"


def sidebar_panel(account: GarminAccount) -> None:
    """Estado de la conexión, botón de sincronizar y formulario de inicio de sesión."""
    with st.sidebar:
        st.markdown("**⌚ Garmin Connect**")

        if account.is_connected:
            last = read_state().get("last_sync")
            st.caption(
                f"Conectado · descargando salidas desde el {format_date(SYNC_START)}"
                + (f" · última sincronización {_ago(time.time() - last)}" if last else "")
            )
            col1, col2 = st.columns([3, 2])
            if col1.button("🔄 Sincronizar ahora", width="stretch"):
                _run_sync(account)
                st.rerun()
            # Desconectar borra la sesión guardada: se pide confirmación para evitar clics accidentales
            with col2.popover("Desconectar", width="stretch"):
                st.caption("Se borrará la sesión guardada y tendrás que volver a iniciar sesión.")
                if st.button("Sí, desconectar", type="primary", width="stretch"):
                    account.disconnect()
                    st.rerun()

        elif account.waiting_for_mfa:
            with st.form("garmin_mfa"):
                code = st.text_input("Código de verificación", help="Garmin te lo envió por correo o SMS.")
                if st.form_submit_button("Verificar", type="primary", width="stretch") and code:
                    try:
                        account.finish_mfa(code)
                        st.session_state.pop("garmin_synced", None)  # Fuerza la primera sincronización
                    except Exception as exc:
                        st.error(f"Código rechazado: {exc}")
                        st.stop()
                    st.rerun()

        else:
            with st.expander("Conectar cuenta", expanded=False):
                st.caption(
                    "Tu contraseña solo se usa para iniciar sesión y no se guarda. "
                    "Se guarda la sesión en `.secrets/garmin/` (excluida de git)."
                )
                with st.form("garmin_login"):
                    email = st.text_input("Correo de Garmin")
                    password = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Conectar", type="primary", width="stretch") and email and password:
                        try:
                            with st.spinner("Iniciando sesión en Garmin..."):
                                account.start_login(email, password)
                            st.session_state.pop("garmin_synced", None)
                        except Exception as exc:
                            st.error(f"No se pudo iniciar sesión: {exc}")
                            st.stop()
                        st.rerun()

        st.divider()
