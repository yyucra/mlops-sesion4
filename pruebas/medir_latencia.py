"""Mide la latencia de la API desde fuera, como la percibe la aplicacion que la consulta.

Uso:  python pruebas/medir_latencia.py                       (100 consultas a http://localhost:8000)
      python pruebas/medir_latencia.py --url http://localhost:8001 --n 200
"""
import argparse
import statistics
import time

import requests

CLIENTE = {"antiguedad_meses": 8, "cargo_mensual": 95.5, "reclamos_ultimo_anio": 3, "contrato_anual": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--objetivo", type=float, default=200, help="latencia maxima del 95%% de las consultas, en ms")
    a = p.parse_args()
    sesion = requests.Session()
    tiempos = []
    for _ in range(a.n):
        inicio = time.perf_counter()
        r = sesion.post(f"{a.url}/predecir", json=CLIENTE, timeout=10)
        r.raise_for_status()
        tiempos.append((time.perf_counter() - inicio) * 1000)
    tiempos.sort()
    p95 = tiempos[int(len(tiempos) * 0.95) - 1]
    print(f"Consultas: {a.n}   respuesta: {r.json()}")
    print(f"Latencia mediana: {statistics.median(tiempos):.1f} ms   p95: {p95:.1f} ms   maxima: {tiempos[-1]:.1f} ms")
    print(("CUMPLE" if p95 < a.objetivo else "NO CUMPLE") + f" el objetivo de {a.objetivo:.0f} ms para el 95% de las consultas")


if __name__ == "__main__":
    main()
