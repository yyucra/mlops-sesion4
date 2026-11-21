"""Vuelve atras: el alias champion regresa a la version anterior.

Uso:  python canary/volver_atras.py
"""
import os

import mlflow
from mlflow import MlflowClient

NOMBRE = os.environ.get("MODELO", "modelo_fuga")


def main():
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    c = MlflowClient()
    actual = c.get_model_version_by_alias(NOMBRE, "champion").version
    anterior = c.get_model_version_by_alias(NOMBRE, "anterior").version
    c.set_registered_model_alias(NOMBRE, "champion", anterior)
    c.set_registered_model_alias(NOMBRE, "challenger", actual)
    c.delete_registered_model_alias(NOMBRE, "anterior")
    print(f"champion vuelve a la version {anterior}. La version {actual} queda otra vez como challenger.")
    print("Para que la API lo cargue sin reiniciarse:")
    print("  curl -X POST localhost:8000/canary -H 'Content-Type: application/json' -d '{\"porcentaje\": 0}'")


if __name__ == "__main__":
    main()
