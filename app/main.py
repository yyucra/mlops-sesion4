"""API del modelo de fuga de clientes (sesion 4).

Carga modelo_fuga@champion desde el Model Registry de MLflow al iniciar y responde
predicciones en linea. Con PORCENTAJE_RETADOR > 0 envia esa parte de las consultas
al modelo con alias challenger (liberacion canary).

Variables de entorno:
  MLFLOW_TRACKING_URI   servidor de MLflow (por defecto http://localhost:5000)
  MODELO                nombre del modelo registrado (por defecto modelo_fuga)
  MODELO_URI            carpeta de un modelo local; si existe, no se usa el registro (pruebas)
  PORCENTAJE_RETADOR    porcentaje de consultas para el retador al iniciar, de 0 a 100 (por defecto 0)
                        Despues se cambia con POST /canary, sin reiniciar (lo usa el DAG de Airflow).
  CANARY_SEMILLA        semilla del reparto, para que el laboratorio sea repetible (por defecto 42)
  API_CLAVE             si se define, cada consulta debe enviar la cabecera X-API-Clave
"""
import os
import random
import time
from contextlib import asynccontextmanager

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, Header, HTTPException
from mlflow import MlflowClient
from pydantic import BaseModel, Field

UMBRAL = 0.5
VARIABLES = ["antiguedad_meses", "cargo_mensual", "reclamos_ultimo_anio", "contrato_anual"]


class Cliente(BaseModel):
    antiguedad_meses: int = Field(ge=0, le=600, description="Meses como cliente")
    cargo_mensual: float = Field(gt=0, description="Cargo mensual en soles")
    reclamos_ultimo_anio: int = Field(ge=0, description="Reclamos en los ultimos 12 meses")
    contrato_anual: bool = Field(description="Tiene contrato anual")


class Canary(BaseModel):
    porcentaje: float = Field(ge=0, le=100, description="Porcentaje de consultas para el retador")


class Prediccion(BaseModel):
    probabilidad_fuga: float
    ofrecer_retencion: bool
    version_modelo: str


modelos = {}      # rol ("campeon" o "retador") -> (version, modelo)
registro = {}     # version -> contadores para el reporte del canary
config = {}


def cargar(nombre, alias):
    version = MlflowClient().get_model_version_by_alias(nombre, alias).version
    return version, mlflow.sklearn.load_model(f"models:/{nombre}/{version}")


def configurar_canary(porcentaje):
    """Carga desde el registro el campeon y, si el porcentaje es mayor que 0, el retador."""
    campeon = cargar(config["nombre"], "champion")
    retador = cargar(config["nombre"], "challenger") if porcentaje > 0 else None
    modelos["campeon"] = campeon
    if retador:
        modelos["retador"] = retador
    else:
        modelos.pop("retador", None)
    config["porcentaje"] = porcentaje
    config["azar"] = random.Random(int(os.environ.get("CANARY_SEMILLA", "42")))
    registro.clear()


@asynccontextmanager
async def ciclo_de_vida(app):
    # El modelo se carga UNA vez, al iniciar el servicio, no en cada consulta.
    config["nombre"] = os.environ.get("MODELO", "modelo_fuga")
    config["clave"] = os.environ.get("API_CLAVE")
    config["local"] = os.environ.get("MODELO_URI")
    if config["local"]:
        modelos["campeon"] = ("local", mlflow.sklearn.load_model(config["local"]))
        config["porcentaje"] = 0
    else:
        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        configurar_canary(float(os.environ.get("PORCENTAJE_RETADOR", "0")))
    yield
    modelos.clear()
    registro.clear()


app = FastAPI(title="API de fuga de clientes", version="1.0.0", lifespan=ciclo_de_vida)


def revisar_clave(clave):
    if config.get("clave") and clave != config["clave"]:
        raise HTTPException(status_code=401, detail="Falta la clave de API o no es valida")


def elegir_rol():
    if "retador" in modelos and config["azar"].random() * 100 < config["porcentaje"]:
        return "retador"
    return "campeon"


def anotar(version, ms=None, oferta=None, error=False):
    r = registro.setdefault(version, {"consultas": 0, "errores": 0, "ofertas": 0, "latencias_ms": []})
    r["consultas"] += 1
    r["errores"] += int(error)
    if not error:
        r["ofertas"] += int(oferta)
        r["latencias_ms"].append(ms)


def predecir_con(rol, clientes):
    version, modelo = modelos[rol]
    X = pd.DataFrame([c.model_dump() for c in clientes])[VARIABLES]
    X["contrato_anual"] = X["contrato_anual"].astype(int)
    probabilidades = modelo.predict_proba(X)[:, 1]
    return [Prediccion(probabilidad_fuga=round(float(p), 4), ofrecer_retencion=bool(p >= UMBRAL),
                       version_modelo=version) for p in probabilidades]


@app.get("/salud")
def salud():
    """Lo consulta el balanceador: el servicio esta vivo y el modelo cargado."""
    return {"estado": "ok", "modelo_cargado": "campeon" in modelos}


@app.get("/info")
def info():
    """Version del modelo y de la API en servicio."""
    return {"modelo": config.get("nombre"), "version_campeon": modelos["campeon"][0],
            "version_retador": modelos["retador"][0] if "retador" in modelos else None,
            "porcentaje_retador": config.get("porcentaje", 0), "version_api": app.version}


@app.post("/predecir", response_model=Prediccion)
def predecir(cliente: Cliente, x_api_clave: str | None = Header(default=None)):
    """Probabilidad de fuga de un cliente y si conviene ofrecerle retencion."""
    revisar_clave(x_api_clave)
    rol = elegir_rol()
    inicio = time.perf_counter()
    try:
        respuesta = predecir_con(rol, [cliente])[0]
    except Exception:
        anotar(modelos[rol][0], error=True)
        raise HTTPException(status_code=500, detail="El modelo no pudo responder")
    anotar(respuesta.version_modelo, (time.perf_counter() - inicio) * 1000, respuesta.ofrecer_retencion)
    return respuesta


@app.post("/predecir-lote", response_model=list[Prediccion])
def predecir_lote(clientes: list[Cliente], x_api_clave: str | None = Header(default=None)):
    """Lo mismo para una lista de clientes. Siempre responde el campeon."""
    revisar_clave(x_api_clave)
    return predecir_con("campeon", clientes)


@app.post("/canary")
def canary(cambio: Canary, x_api_clave: str | None = Header(default=None)):
    """Cambia el porcentaje del retador y recarga los modelos desde el registro, sin reiniciar.

    Con 0 el retador deja de recibir consultas. Tambien sirve para cargar un campeon recien promovido.
    Reinicia el reporte de /metricas.
    """
    revisar_clave(x_api_clave)
    if config.get("local"):
        raise HTTPException(status_code=409, detail="La API usa un modelo local: no hay registro que recargar")
    configurar_canary(cambio.porcentaje)
    return info()


@app.get("/metricas")
def metricas():
    """Consultas, errores, ofertas y latencia por version del modelo (reporte del canary)."""
    salida = {}
    for version, r in registro.items():
        lat = sorted(r["latencias_ms"])
        exitosas = r["consultas"] - r["errores"]
        salida[version] = {
            "consultas": r["consultas"],
            "errores_pct": round(100 * r["errores"] / r["consultas"], 2),
            "ofertas_pct": round(100 * r["ofertas"] / exitosas, 1) if exitosas else 0.0,
            "latencia_p95_ms": round(lat[max(0, int(len(lat) * 0.95) - 1)], 2) if lat else None,
        }
    return salida
