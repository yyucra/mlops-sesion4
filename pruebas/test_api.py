"""Pruebas de la API: la compuerta de calidad antes de publicar una version nueva."""
import time
from pathlib import Path

import pandas as pd
import pytest

CLIENTE = {"antiguedad_meses": 8, "cargo_mensual": 95.5, "reclamos_ultimo_anio": 3, "contrato_anual": False}


# ---------- Unitarias ----------
def test_servicio_vivo(api):
    assert api.get("/salud").json() == {"estado": "ok", "modelo_cargado": True}


def test_probabilidad_entre_0_y_1(api):
    datos = pd.read_csv(Path(__file__).parents[1] / "datos" / "clientes.csv").dropna().head(50)
    for _, c in datos.iterrows():
        r = api.post("/predecir", json={"antiguedad_meses": int(c.antiguedad_meses), "cargo_mensual": float(c.cargo_mensual),
                                       "reclamos_ultimo_anio": int(c.reclamos_ultimo_anio), "contrato_anual": c.contrato_anual == "si"})
        assert r.status_code == 200
        assert 0 <= r.json()["probabilidad_fuga"] <= 1


# ---------- Contrato ----------
@pytest.mark.parametrize("cambio", [
    {"antiguedad_meses": -5},          # antiguedad negativa
    {"cargo_mensual": 0},              # cargo no positivo
    {"reclamos_ultimo_anio": "muchos"},  # texto donde va un numero
])
def test_datos_invalidos_devuelven_422(api, cambio):
    assert api.post("/predecir", json={**CLIENTE, **cambio}).status_code == 422


def test_campo_faltante_devuelve_422(api):
    incompleto = {k: v for k, v in CLIENTE.items() if k != "contrato_anual"}
    assert api.post("/predecir", json=incompleto).status_code == 422


def test_respuesta_tiene_el_formato_acordado(api):
    assert set(api.post("/predecir", json=CLIENTE).json()) == {"probabilidad_fuga", "ofrecer_retencion", "version_modelo"}


# ---------- Modelo ----------
@pytest.mark.parametrize("cliente, probabilidad, ofrecer", [
    (CLIENTE, 0.8776, True),
    ({"antiguedad_meses": 68, "cargo_mensual": 50.82, "reclamos_ultimo_anio": 2, "contrato_anual": True}, 0.0545, False),
    ({"antiguedad_meses": 30, "cargo_mensual": 75.0, "reclamos_ultimo_anio": 0, "contrato_anual": False}, 0.5615, True),
])
def test_clientes_de_referencia(api, cliente, probabilidad, ofrecer):
    r = api.post("/predecir", json=cliente).json()
    assert r["probabilidad_fuga"] == pytest.approx(probabilidad, abs=0.001)
    assert r["ofrecer_retencion"] is ofrecer


def test_lote_responde_un_resultado_por_cliente(api):
    assert len(api.post("/predecir-lote", json=[CLIENTE] * 5).json()) == 5


# ---------- Desempeno ----------
def test_latencia_de_100_consultas(api):
    tiempos = []
    for _ in range(100):
        inicio = time.perf_counter()
        api.post("/predecir", json=CLIENTE)
        tiempos.append((time.perf_counter() - inicio) * 1000)
    p95 = sorted(tiempos)[94]
    assert p95 < 200, f"el 95% de las consultas tarda hasta {p95:.0f} ms (objetivo: 200 ms)"
