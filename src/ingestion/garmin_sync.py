"""Sincronización incremental de actividades desde Garmin Connect.

Usa la librería no oficial `garminconnect` para descargar el archivo FIT original
de cada salida en bici. Los archivos se guardan junto a los demás FIT, así que el
resto del pipeline (lectura, métricas, gráficos) no cambia.
"""
from __future__ import annotations

import io
import json
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from garminconnect import Garmin, GarminConnectTooManyRequestsError

ROOT = Path(__file__).resolve().parents[2]
TOKENS_DIR = ROOT / ".secrets" / "garmin"
FIT_FOLDER = ROOT / "data" / "raw" / "fit"
STATE_NAME = "_garmin_sync.json"

SYNC_START = date(2026, 9, 25)  # Primera fecha que se descarga
LOOKBACK_DAYS = 7               # Revisa la última semana por si algo se subió con retraso

RIDE_KEYWORDS = ("cycling", "biking", "virtual_ride", "cyclocross", "bmx")


@dataclass
class SyncResult:
    new: list[str] = field(default_factory=list)
    skipped: int = 0
    error: str | None = None


class GarminAccount:
    """Sesión de Garmin Connect.

    La contraseña solo se usa para el primer inicio de sesión y nunca se guarda;
    lo que se guarda son los tokens de sesión en `.secrets/garmin/`.
    """

    def __init__(self, tokens_dir: Path = TOKENS_DIR):
        self.tokens_dir = tokens_dir
        self._api: Garmin | None = None
        self._pending_mfa: tuple[Garmin, object] | None = None

    @property
    def is_connected(self) -> bool:
        return self.tokens_dir.exists() and any(self.tokens_dir.iterdir())

    @property
    def waiting_for_mfa(self) -> bool:
        return self._pending_mfa is not None

    def api(self) -> Garmin:
        """Cliente autenticado a partir de los tokens guardados."""
        if self._api is None:
            api = Garmin()
            api.login(str(self.tokens_dir))
            self._api = api
        return self._api

    def start_login(self, email: str, password: str) -> bool:
        """Inicia sesión. Retorna True si Garmin pide el código de verificación (MFA)."""
        api = Garmin(email.strip(), password, return_on_mfa=True)
        status, client_state = api.login()
        if status == "needs_mfa":
            self._pending_mfa = (api, client_state)
            return True
        self._save_tokens(api)
        return False

    def finish_mfa(self, code: str) -> None:
        api, client_state = self._pending_mfa
        api.resume_login(client_state, code.strip())
        self._pending_mfa = None
        self._save_tokens(api)

    def _save_tokens(self, api: Garmin) -> None:
        api.client.dump(str(self.tokens_dir))
        self._api = None  # La próxima llamada a api() carga el perfil desde los tokens

    def disconnect(self) -> None:
        shutil.rmtree(self.tokens_dir, ignore_errors=True)
        self._api = None


def is_ride(activity: dict) -> bool:
    key = (activity.get("activityType") or {}).get("typeKey", "")
    return any(word in key for word in RIDE_KEYWORDS)


def extract_fit(data: bytes) -> bytes | None:
    """Garmin entrega el original como zip; dentro viene el .fit."""
    if data[8:12] == b".FIT":  # Ya es un FIT sin comprimir
        return data
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                if name.lower().endswith(".fit"):
                    return archive.read(name)
    except zipfile.BadZipFile:
        pass
    return None  # Actividad manual o importada en otro formato (GPX, TCX)


def read_state(folder: Path = FIT_FOLDER) -> dict:
    path = folder / STATE_NAME
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_state(folder: Path, state: dict) -> None:
    (folder / STATE_NAME).write_text(json.dumps(state, indent=2), encoding="utf-8")


def sync_activities(
    api: Garmin,
    folder: Path = FIT_FOLDER,
    since: date = SYNC_START,
    until: date | None = None,
) -> SyncResult:
    """Descarga los FIT de las salidas en bici que aún no están en disco.

    Se procesan en orden cronológico y se guardan uno a uno: si se corta por el
    límite de peticiones, la próxima ejecución continúa donde quedó.
    """
    folder.mkdir(parents=True, exist_ok=True)
    state = read_state(folder)
    result = SyncResult()

    start = since
    if state.get("latest_start"):
        latest = datetime.fromisoformat(state["latest_start"]).date()
        start = max(since, latest - timedelta(days=LOOKBACK_DAYS))
    # Hasta mañana: Garmin no documenta si la fecha final es inclusiva y la salida de hoy debe entrar
    until = until or date.today() + timedelta(days=1)

    try:
        activities = api.get_activities_by_date(start.isoformat(), until.isoformat())
        for summary in sorted(activities, key=lambda a: a.get("startTimeLocal", "")):
            path = folder / f"garmin_{summary['activityId']}.fit"
            if path.exists() or not is_ride(summary):
                result.skipped += 1
                continue

            fit = extract_fit(api.download_activity(
                summary["activityId"], dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL,
            ))
            if fit is None:
                result.skipped += 1
                continue

            path.write_bytes(fit)
            result.new.append(summary.get("activityName") or str(summary["activityId"]))
            state["latest_start"] = max(state.get("latest_start", ""), summary.get("startTimeLocal", ""))
            _write_state(folder, state)

    except GarminConnectTooManyRequestsError:
        result.error = "Garmin limitó las peticiones; vuelve a intentarlo en unos minutos."
    except Exception as exc:  # Red caída, sesión expirada, etc.: no debe tumbar el dashboard
        result.error = f"No se pudo sincronizar con Garmin: {exc}"

    state["last_sync"] = time.time()
    _write_state(folder, state)
    return result
