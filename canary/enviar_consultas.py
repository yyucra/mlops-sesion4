"""Envia consultas a la API, como lo haria el CRM, y muestra el reporte por version.

Uso:  python canary/enviar_consultas.py              (200 consultas a http://localhost:8000)
      python canary/enviar_consultas.py --n 500 --url http://localhost:8001
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]


def enviar(url, n):
    """Envia n consultas con clientes reales y devuelve cuantas fallaron. La usa tambien el DAG de Airflow."""
    clientes = pd.read_csv(RAIZ / "datos" / "clientes.csv").sample(n, replace=True, random_state=7)
    fallidas = 0
    for _, c in clientes.iterrows():
        cuerpo = {"antiguedad_meses": int(c.antiguedad_meses), "cargo_mensual": float(c.cargo_mensual),
                  "reclamos_ultimo_anio": int(c.reclamos_ultimo_anio), "contrato_anual": c.contrato_anual == "si"}
        if pd.isna(c.cargo_mensual):
            cuerpo["cargo_mensual"] = 70.0   # el CRM completa el dato faltante con un valor tipico
        r = requests.post(f"{url}/predecir", json=cuerpo, timeout=10)
        fallidas += r.status_code != 200
    return fallidas


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--url", default="http://localhost:8000")
    a = p.parse_args()
    fallidas = enviar(a.url, a.n)
    print(f"Consultas enviadas: {a.n}   con error: {fallidas}\n")
    info = requests.get(f"{a.url}/info", timeout=10).json()
    reporte = requests.get(f"{a.url}/metricas", timeout=10).json()
    print(f"{'Version':<10}{'Rol':<10}{'Consultas':>10}{'Errores %':>11}{'Ofertas %':>11}{'Latencia p95':>14}")
    for version, m in sorted(reporte.items()):
        rol = "campeon" if version == info["version_campeon"] else "retador"
        print(f"{version:<10}{rol:<10}{m['consultas']:>10}{m['errores_pct']:>11}{m['ofertas_pct']:>11}{str(m['latencia_p95_ms']) + ' ms':>14}")
    sys.exit(1 if fallidas else 0)


if __name__ == "__main__":
    main()
