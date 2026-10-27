"""Sincroniza las salidas de Garmin Connect sin abrir el dashboard.

Uso:  python scripts/sync_garmin.py
La primera vez pide correo, contraseña y (si aplica) el código de verificación.
"""
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.garmin_sync import GarminAccount, sync_activities


def main() -> int:
    account = GarminAccount()
    if not account.is_connected:
        email = input("Correo de Garmin: ")
        if account.start_login(email, getpass("Contraseña: ")):
            account.finish_mfa(input("Código de verificación: "))
        print("Sesión guardada en .secrets/garmin/")

    result = sync_activities(account.api())
    for name in result.new:
        print(f"  + {name}")
    print(f"{len(result.new)} nuevas, {result.skipped} ya descargadas u omitidas.")
    if result.error:
        print(f"Aviso: {result.error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
