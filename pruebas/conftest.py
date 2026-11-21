"""Configuracion comun de las pruebas: usan el modelo de referencia local, sin MLflow."""
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["MODELO_URI"] = str(Path(__file__).parent / "modelo_referencia")
os.environ.pop("API_CLAVE", None)
os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def api():
    with TestClient(app) as cliente:
        yield cliente
