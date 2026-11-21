"""Verifica el entorno de la sesion 4: versiones, datos, MLflow, modelos registrados y Docker.

Uso:  python entorno/verificar.py            (una sola revision)
      python entorno/verificar.py --esperar  (reintenta hasta 3 minutos)
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HUELLA = "f74f4cec5c10682fc01ddd3cd35b5715"
CLAVE_AIRFLOW = BASE / "entorno" / "estado" / "airflow" / "simple_auth_manager_passwords.json.generated"


def paquetes(archivo):
    for linea in (BASE / archivo).read_text().splitlines():
        linea = linea.strip()
        if linea.startswith("-r "):
            yield from paquetes(linea[3:])
        elif "==" in linea and not linea.startswith("#"):
            yield linea.split("==")


def http_json(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read() or b"{}") if r.status == 200 else None
    except Exception:
        return None


def http_ok(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def alias(nombre):
    datos = http_json(f"http://localhost:5000/api/2.0/mlflow/registered-models/alias?name=modelo_fuga&alias={nombre}")
    return datos["model_version"]["version"] if datos else None


def docker_listo():
    try:
        r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def dag_activo():
    """Pregunta a Airflow si el DAG liberacion_canary esta cargado y activo."""
    try:
        usuario, contrasena = next(iter(json.loads(CLAVE_AIRFLOW.read_text()).items()))
        pedido = urllib.request.Request("http://localhost:8080/auth/token", method="POST",
                                        data=json.dumps({"username": usuario, "password": contrasena}).encode(),
                                        headers={"Content-Type": "application/json"})
        token = json.loads(urllib.request.urlopen(pedido, timeout=5).read())["access_token"]
        pedido = urllib.request.Request("http://localhost:8080/api/v2/dags/liberacion_canary",
                                        headers={"Authorization": f"Bearer {token}"})
        return not json.loads(urllib.request.urlopen(pedido, timeout=5).read())["is_paused"]
    except Exception:
        return False


def revisar():
    filas = []
    v = sys.version_info
    filas.append(("Python 3.12 o 3.13", f"{v.major}.{v.minor}.{v.micro}", (3, 12) <= v[:2] <= (3, 13)))
    for paquete, esperada in paquetes("requirements-dev.txt"):
        try:
            instalada = version(paquete)
        except PackageNotFoundError:
            instalada = "no instalado"
        filas.append((paquete, instalada, instalada == esperada))
    datos = BASE / "datos" / "clientes.csv"
    huella = hashlib.md5(datos.read_bytes()).hexdigest() if datos.exists() else "no existe"
    filas.append(("Datos clientes.csv", huella[:8], huella == HUELLA))
    filas.append(("Modelo de referencia de las pruebas", "", (BASE / "pruebas" / "modelo_referencia" / "MLmodel").exists()))
    filas.append(("MLflow      http://localhost:5000", "", http_ok("http://localhost:5000/health")))
    campeon, retador = alias("champion"), alias("challenger")
    filas.append(("modelo_fuga@champion", f"version {campeon}" if campeon else "", campeon is not None))
    filas.append(("modelo_fuga@challenger", f"version {retador}" if retador else "", retador is not None))
    filas.append(("Airflow     http://localhost:8080", "", http_ok("http://localhost:8080/api/v2/monitor/health")))
    filas.append(("DAG liberacion_canary activo", "", dag_activo()))
    servidor = docker_listo()
    filas.append(("Docker", servidor, bool(servidor)))
    return filas


def main():
    limite = time.time() + (180 if "--esperar" in sys.argv else 0)
    while True:
        filas = revisar()
        if all(ok for *_, ok in filas) or time.time() > limite:
            break
        time.sleep(5)
    print()
    for nombre, valor, ok in filas:
        print(f"  [{'OK' if ok else 'X '}] {nombre:<38} {valor}")
    if os.environ.get("CODESPACE_NAME"):
        dominio = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
        print("\n  Direcciones en el navegador (pestana PORTS de Codespaces):")
        print(f"  MLflow      https://{os.environ['CODESPACE_NAME']}-5000.{dominio}")
        print(f"  Airflow     https://{os.environ['CODESPACE_NAME']}-8080.{dominio}")
        print(f"  API         https://{os.environ['CODESPACE_NAME']}-8000.{dominio}/docs   (cuando la inicie)")
    else:
        print("\n  MLflow      http://localhost:5000")
        print("  Airflow     http://localhost:8080")
        print("  API         http://localhost:8000/docs   (cuando la inicie)")
    if CLAVE_AIRFLOW.exists():
        usuario, contrasena = next(iter(json.loads(CLAVE_AIRFLOW.read_text()).items()))
        print(f"\n  Airflow     usuario: {usuario}   contrasena: {contrasena}")
    fallos = [n for n, _, ok in filas if not ok]
    print("\nENTORNO LISTO" if not fallos else f"\nREVISAR: {', '.join(fallos)}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    os.chdir(BASE)
    main()
