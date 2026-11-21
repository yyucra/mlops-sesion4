"""(Docente) Crea pruebas/modelo_referencia: una copia local del campeon (profundidad 4, hoja 43).

Las pruebas automaticas y GitHub Actions la usan para no depender de un servidor de MLflow.
"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import mlflow.sklearn
import pandas as pd
from comun import fuga

destino = RAIZ / "pruebas" / "modelo_referencia"
shutil.rmtree(destino, ignore_errors=True)
X_ent, X_val, X_pro, y_ent, y_val, y_pro = fuga.dividir(fuga.cargar_datos())
modelo = fuga.entrenar(pd.concat([X_ent, X_val]), pd.concat([y_ent, y_val]), 4, 43)
mlflow.sklearn.save_model(modelo, destino, skops_trusted_types=["sklearn.tree._tree.Tree"])
print("Modelo de referencia guardado en", destino, "| beneficio:", fuga.metricas(modelo, X_pro, y_pro)["beneficio_neto"])
