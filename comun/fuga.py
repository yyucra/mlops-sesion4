"""Funciones comunes del caso de fuga de clientes (sesiones 3 y 4).

En la sesion 4 las usa entorno/preparar_modelos.py para reproducir el registro
de modelos de la sesion 3 con los mismos datos y la misma semilla.
"""
import os
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(os.environ.get("DATOS_FUGA", RAIZ / "datos" / "clientes.csv"))

# Supuestos economicos del caso (ilustrativos)
VALOR_CLIENTE = 1200   # soles que aporta un cliente retenido en un anio
COSTO_OFERTA = 60      # soles que cuesta la oferta de retencion
UMBRAL = 0.5           # probabilidad a partir de la cual se ofrece retencion
SEMILLA = 42
VARIABLES = ["antiguedad_meses", "cargo_mensual", "reclamos_ultimo_anio", "contrato_anual"]


def cargar_datos(ruta=DATOS):
    df = pd.read_csv(ruta)
    df["contrato_anual"] = (df["contrato_anual"] == "si").astype(int)
    df["fuga"] = (df["fuga"] == "si").astype(int)
    return df


def validar(df):
    """Reglas de calidad de la sesion 2. Devuelve la lista de reglas que fallan."""
    reglas = {
        "cargo mensual completo (>= 98%)": df["cargo_mensual"].notna().mean() >= 0.98,
        "clientes unicos": df["cliente_id"].is_unique,
        "antiguedad valida": df["antiguedad_meses"].between(0, 600).all(),
        "etiqueta disponible": df["fuga"].isin([0, 1]).all(),
        "al menos 500 registros": len(df) >= 500,
    }
    return [nombre for nombre, cumple in reglas.items() if not cumple]


def dividir(df):
    """70% entrenamiento, 15% validacion, 15% evaluacion de promocion (X_pru).
    Siempre la misma division (semilla 42). La evaluacion de promocion nunca se usa para optimizar."""
    X, y = df[VARIABLES], df["fuga"]
    X_ent, X_resto, y_ent, y_resto = train_test_split(X, y, test_size=0.30, random_state=SEMILLA, stratify=y)
    X_val, X_pru, y_val, y_pru = train_test_split(X_resto, y_resto, test_size=0.50, random_state=SEMILLA, stratify=y_resto)
    return X_ent, X_val, X_pru, y_ent, y_val, y_pru


def entrenar(X, y, profundidad, min_hoja):
    modelo = DecisionTreeClassifier(max_depth=profundidad, min_samples_leaf=min_hoja, random_state=SEMILLA)
    return modelo.fit(X, y)


def metricas(modelo, X, y):
    """Metricas tecnicas y beneficio neto en soles."""
    pred = (modelo.predict_proba(X)[:, 1] >= UMBRAL).astype(int)
    vp = int(((pred == 1) & (y == 1)).sum())   # se iba y lo detectamos
    fp = int(((pred == 1) & (y == 0)).sum())   # falsa alarma
    fn = int(((pred == 0) & (y == 1)).sum())   # se iba y no lo detectamos
    vn = int(((pred == 0) & (y == 0)).sum())
    return {
        "exactitud": round((vp + vn) / len(y), 4),
        "precision": round(vp / (vp + fp), 4) if vp + fp else 0.0,
        "sensibilidad": round(vp / (vp + fn), 4) if vp + fn else 0.0,
        "beneficio_neto": vp * (VALOR_CLIENTE - COSTO_OFERTA) - fp * COSTO_OFERTA,
    }
