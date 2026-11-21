"""Promueve al retador: el alias champion pasa a la version challenger.

La version que era campeona queda con el alias anterior, para poder volver atras.
Uso:  python canary/promover.py --aprobado-por "Ana Torres"
"""
import argparse
import os
from datetime import datetime

import mlflow
from mlflow import MlflowClient

NOMBRE = os.environ.get("MODELO", "modelo_fuga")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--aprobado-por", required=True, help="Nombre de quien aprueba en el negocio")
    a = p.parse_args()
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    c = MlflowClient()
    campeon = c.get_model_version_by_alias(NOMBRE, "champion").version
    retador = c.get_model_version_by_alias(NOMBRE, "challenger").version
    c.set_registered_model_alias(NOMBRE, "anterior", campeon)
    c.set_registered_model_alias(NOMBRE, "champion", retador)
    c.delete_registered_model_alias(NOMBRE, "challenger")
    c.set_model_version_tag(NOMBRE, retador, "aprobado_por", a.aprobado_por)
    c.set_model_version_tag(NOMBRE, retador, "aprobado_en", datetime.now().isoformat(timespec="minutes"))
    print(f"Version {retador} promovida a champion. La version {campeon} queda como anterior.")
    print("Para que la API lo cargue sin reiniciarse:")
    print("  curl -X POST localhost:8000/canary -H 'Content-Type: application/json' -d '{\"porcentaje\": 0}'")


if __name__ == "__main__":
    main()
