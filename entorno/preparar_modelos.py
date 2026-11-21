"""Reproduce el registro de modelos de la sesion 3 en el MLflow de la sesion 4.

Con los mismos datos y la misma semilla, entrena y registra tres versiones de modelo_fuga:
  v1  profundidad 2, hoja minima 5    primer campeon de la sesion 3
  v2  profundidad 4, hoja minima 43   campeon aprobado en la sesion 3   -> alias champion
  v3  profundidad 4, hoja minima 37   retador del entrenamiento semanal -> alias challenger

Si el modelo ya esta registrado, no hace nada.
"""
import contextlib
import hashlib
import io
import logging
import os
import warnings
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient

from comun import fuga

warnings.filterwarnings("ignore")
logging.getLogger("mlflow").setLevel(logging.ERROR)

NOMBRE = "modelo_fuga"
VERSIONES = [
    (2, 5, None, "Primer campeon de la sesion 3"),
    (4, 43, "champion", "Campeon aprobado en la sesion 3"),
    (4, 37, "challenger", "Retador del entrenamiento semanal siguiente"),
]


def main():
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    cliente = MlflowClient()
    if cliente.search_registered_models(filter_string=f"name='{NOMBRE}'"):
        print(f"{NOMBRE} ya esta registrado: no se cambia nada.")
        return
    df = fuga.cargar_datos()
    X_ent, X_val, X_pro, y_ent, y_val, y_pro = fuga.dividir(df)
    X, y = pd.concat([X_ent, X_val]), pd.concat([y_ent, y_val])
    huella = hashlib.md5(fuga.DATOS.read_bytes()).hexdigest()
    mlflow.set_experiment("registro_modelo_fuga")
    print(f"{'Version':<8}{'Profundidad':<13}{'Hoja min.':<11}{'Beneficio':<12}Alias")
    for profundidad, hoja, alias, descripcion in VERSIONES:
        silencio = io.StringIO()
        with contextlib.redirect_stdout(silencio), contextlib.redirect_stderr(silencio), \
                mlflow.start_run(run_name=f"arbol_p{profundidad}_h{hoja}"):
            modelo = fuga.entrenar(X, y, profundidad, hoja)
            resultado = fuga.metricas(modelo, X_pro, y_pro)
            mlflow.log_params({"profundidad": profundidad, "min_hoja": hoja})
            mlflow.log_metrics({f"promocion_{k}": v for k, v in resultado.items()})
            mlflow.set_tags({"version_datos": huella, "origen": "preparar_modelos.py"})
            info = mlflow.sklearn.log_model(modelo, name="modelo", input_example=X_pro.head(3),
                                            registered_model_name=NOMBRE,
                                            skops_trusted_types=["sklearn.tree._tree.Tree"])
        version = str(info.registered_model_version)
        cliente.update_model_version(NOMBRE, version, description=descripcion)
        if alias:
            cliente.set_registered_model_alias(NOMBRE, alias, version)
        print(f"{version:<8}{profundidad:<13}{hoja:<11}S/ {resultado['beneficio_neto']:<9,}{alias or ''}".replace(",", " "))


if __name__ == "__main__":
    main()
