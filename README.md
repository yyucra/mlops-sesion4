# MLOps · Sesión 4 · Despliegue de modelos

API del modelo de fuga de clientes con FastAPI, imagen Docker, pruebas con pytest,
integración continua con GitHub Actions y liberación canary orquestada por Apache Airflow.

## Instalación

Dos opciones: **GitHub Codespaces** (en la nube, con Docker incluido) o **Ubuntu en WSL**
(en Windows; Docker se instala con `sudo apt install -y docker.io`). En la terminal, dentro de la carpeta:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
bash entorno/iniciar.sh
```

La verificación debe terminar con `ENTORNO LISTO`.

| Servicio | Puerto | Cómo se inicia |
| --- | --- | --- |
| MLflow | 5000 | `bash entorno/iniciar.sh` |
| Airflow | 8080 | `bash entorno/iniciar.sh` (usuario `admin`; contraseña en `python entorno/verificar.py`) |
| API | 8000 | `uvicorn app.main:app --port 8000` (laboratorio 1) |

| Archivo | Para qué |
| --- | --- |
| `requirements.txt` | Dependencias de la API (las instala el Dockerfile) |
| `requirements-dev.txt` | Entorno completo: API, MLflow, Airflow y pruebas |
| `app/main.py` | La API |
| `pruebas/` | Pruebas de pytest y medición de latencia |
| `dags/liberacion_canary.py` | DAG de Airflow: pruebas, canary, compuerta, aprobación, promoción y aviso al CD |
| `canary/` | Envío de consultas, promoción y vuelta atrás |
| `.github/workflows/api.yml` | Integración continua |

Para detener todo: `bash entorno/detener.sh`. La guía de laboratorio de la sesión 4 explica cada paso.
