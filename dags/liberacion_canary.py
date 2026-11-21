"""Liberacion canary del modelo de fuga, orquestada por Airflow (sesion 4, laboratorio 2).

pruebas -> iniciar_canary -> enviar_consultas -> evaluar_compuerta
    -> decision_negocio (una persona decide en Airflow) -> aplicar_decision
        -> promover -> recargar_api -> avisar_cd
        -> revertir (si la compuerta falla o el negocio rechaza)

La API debe estar encendida (uvicorn app.main:app --port 8000). El DAG le cambia el porcentaje
del retador con POST /canary, sin reiniciarla.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pendulum
import requests
from airflow.providers.standard.operators.hitl import HITLOperator
from airflow.sdk import Param, dag, get_current_context, task

BASE = Path(__file__).resolve().parents[1]
MODELO = "modelo_fuga"


def mlflow_cliente():
    import mlflow
    from mlflow import MlflowClient
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    return MlflowClient()


@dag(
    dag_id="liberacion_canary",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="America/Lima"),
    catchup=False,
    tags=["sesion4", "despliegue"],
    params={
        "url_api": Param("http://localhost:8000", type="string", description="Direccion de la API"),
        "porcentaje": Param(20, type="integer", minimum=1, maximum=50, description="Porcentaje para el retador"),
        "consultas": Param(200, type="integer", minimum=50, maximum=2000, description="Consultas del canary"),
        "errores_max_pct": Param(1.0, type="number", description="Compuerta: errores maximos (%)"),
        "latencia_max_ms": Param(200, type="number", description="Compuerta: latencia p95 maxima (ms)"),
    },
)
def liberacion_canary():

    @task
    def pruebas():
        """Compuerta de calidad del codigo: si una prueba falla, no se libera nada."""
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                           cwd=BASE, capture_output=True, text=True)
        print(r.stdout[-3000:])
        if r.returncode != 0:
            raise RuntimeError("Las pruebas fallaron: la version no se libera")

    @task
    def iniciar_canary():
        p = get_current_context()["params"]
        r = requests.post(f"{p['url_api']}/canary", json={"porcentaje": p["porcentaje"]}, timeout=60)
        r.raise_for_status()
        info = r.json()
        print(f"Campeon: version {info['version_campeon']} | retador: version {info['version_retador']} "
              f"al {info['porcentaje_retador']:.0f}%")
        return info

    @task
    def enviar_consultas(info):
        sys.path.insert(0, str(BASE))
        from canary.enviar_consultas import enviar
        p = get_current_context()["params"]
        fallidas = enviar(p["url_api"], p["consultas"])
        reporte = requests.get(f"{p['url_api']}/metricas", timeout=10).json()
        lineas = [f"Consultas: {p['consultas']} (con error: {fallidas})"]
        for version, m in sorted(reporte.items()):
            rol = "campeon" if version == info["version_campeon"] else "retador"
            lineas.append(f"Version {version} ({rol}): {m['consultas']} consultas, {m['errores_pct']}% errores, "
                          f"{m['ofertas_pct']}% ofertas, p95 {m['latencia_p95_ms']} ms")
        resumen = "\n".join(lineas)
        print(resumen)
        return {"info": info, "reporte": reporte, "resumen": resumen}

    @task.branch
    def evaluar_compuerta(resultado):
        """Compuerta tecnica automatica. Si pasa, decide una persona; si no, se revierte."""
        p = get_current_context()["params"]
        retador = resultado["reporte"].get(resultado["info"]["version_retador"])
        if not retador:
            print("El retador no recibio consultas: se revierte")
            return "revertir"
        criterios = {
            f"errores <= {p['errores_max_pct']}%": retador["errores_pct"] <= p["errores_max_pct"],
            f"latencia p95 <= {p['latencia_max_ms']} ms": retador["latencia_p95_ms"] <= p["latencia_max_ms"],
        }
        for nombre, cumple in criterios.items():
            print(f"[{'OK' if cumple else 'X '}] {nombre}")
        return "decision_negocio" if all(criterios.values()) else "revertir"

    decision_negocio = HITLOperator(
        task_id="decision_negocio",
        subject="¿Promover el modelo retador a champion?",
        body="La compuerta tecnica paso. Resultado del canary:\n\n"
             "{{ ti.xcom_pull(task_ids='enviar_consultas')['resumen'] }}\n\n"
             "Escriba su nombre y elija una opcion.",
        options=["Promover", "Rechazar"],
        params={"aprobado_por": Param("", type="string", description="Nombre de quien decide")},
    )

    @task.branch
    def aplicar_decision():
        """Lee la respuesta de la persona y sigue el camino que eligio."""
        respuesta = get_current_context()["ti"].xcom_pull(task_ids="decision_negocio")
        opcion = respuesta["chosen_options"][0]
        nombre = respuesta["params_input"].get("aprobado_por") or "sin nombre"
        print(f"{nombre} eligio: {opcion}")
        return "promover" if opcion == "Promover" else "revertir"

    @task
    def promover():
        """Mueve el alias champion al retador y deja el anterior para poder volver atras."""
        respuesta = get_current_context()["ti"].xcom_pull(task_ids="decision_negocio")
        aprobado_por = respuesta["params_input"].get("aprobado_por") or "sin nombre"
        c = mlflow_cliente()
        campeon = c.get_model_version_by_alias(MODELO, "champion").version
        retador = c.get_model_version_by_alias(MODELO, "challenger").version
        c.set_registered_model_alias(MODELO, "anterior", campeon)
        c.set_registered_model_alias(MODELO, "champion", retador)
        c.delete_registered_model_alias(MODELO, "challenger")
        c.set_model_version_tag(MODELO, retador, "aprobado_por", aprobado_por)
        c.set_model_version_tag(MODELO, retador, "aprobado_en", datetime.now().isoformat(timespec="minutes"))
        c.set_model_version_tag(MODELO, retador, "aprobado_con", "Airflow liberacion_canary")
        print(f"Version {retador} promovida a champion por {aprobado_por}. La version {campeon} queda como anterior.")
        return retador

    @task
    def recargar_api(version):
        """La API carga el nuevo campeon y el retador deja de recibir consultas, sin reiniciar."""
        p = get_current_context()["params"]
        info = requests.post(f"{p['url_api']}/canary", json={"porcentaje": 0}, timeout=60).json()
        print(info)
        if info["version_campeon"] != version:
            raise RuntimeError(f"La API responde con la version {info['version_campeon']}, no con la {version}")
        return version

    @task
    def avisar_cd(version):
        """Avisa al CD en GitHub Actions (evento repository_dispatch) que hay un modelo aprobado."""
        evento = {"event_type": "modelo-aprobado", "client_payload": {"modelo": MODELO, "version": version}}
        token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPO")
        if not (token and repo):
            print("GITHUB_TOKEN y GITHUB_REPO no estan definidos: no se envia el aviso.")
            print("Se enviaria a https://api.github.com/repos/<usuario>/<repositorio>/dispatches:")
            print(json.dumps(evento, ensure_ascii=False))
            return
        r = requests.post(f"https://api.github.com/repos/{repo}/dispatches", json=evento, timeout=30,
                          headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        r.raise_for_status()
        print(f"Aviso enviado a {repo}: GitHub Actions ejecuta el flujo api-fuga")

    @task(trigger_rule="none_failed_min_one_success")
    def revertir():
        """El retador vuelve al 0%: todas las consultas las responde el campeon."""
        p = get_current_context()["params"]
        print(requests.post(f"{p['url_api']}/canary", json={"porcentaje": 0}, timeout=60).json())

    info = iniciar_canary()
    pruebas() >> info
    resultado = enviar_consultas(info)
    compuerta = evaluar_compuerta(resultado)
    fin = revertir()
    compuerta >> [decision_negocio, fin]
    camino = aplicar_decision()
    decision_negocio >> camino
    version = promover()
    camino >> [version, fin]
    avisar_cd(recargar_api(version))


liberacion_canary()
