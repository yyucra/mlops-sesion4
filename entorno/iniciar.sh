#!/usr/bin/env bash
# Inicia MLflow (puerto 5000) y Airflow (8080), registra los modelos de la sesion 3 si faltan
# y verifica el entorno.
# La API (puerto 8000) la inicia cada participante durante el laboratorio.
set -e
BASE="$(cd "$(dirname "$0")/.." && pwd)"
ESTADO="$BASE/entorno/estado"
mkdir -p "$ESTADO/logs"
source "$BASE/.venv/bin/activate"
export MLFLOW_TRACKING_URI=http://localhost:5000 MLFLOW_DISABLE_AGENT_HINT=1
export AIRFLOW_HOME="$ESTADO/airflow"
export AIRFLOW__CORE__DAGS_FOLDER="$BASE/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=False
export AIRFLOW__CORE__PARALLELISM=4          # pocas tareas a la vez: suficiente para un equipo
export AIRFLOW__API__HOST=127.0.0.1         # Airflow solo responde en este equipo
# Las tareas hablan con Airflow por la direccion interna, aunque la interfaz se publique en otra
export AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://localhost:8080/execution/

# En GitHub Codespaces, MLflow debe aceptar la direccion publicada del codespace.
SEGURIDAD=()
if [ -n "${CODESPACE_NAME:-}" ]; then
  DOMINIO="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  export AIRFLOW__API__BASE_URL="https://$CODESPACE_NAME-8080.$DOMINIO"
  SEGURIDAD=(--allowed-hosts "$CODESPACE_NAME-5000.$DOMINIO,localhost,localhost:5000,127.0.0.1,127.0.0.1:5000"
             --cors-allowed-origins "https://$CODESPACE_NAME-5000.$DOMINIO")
fi

arrancar() {   # nombre, comando...
  local nombre=$1; shift
  if [ -f "$ESTADO/$nombre.pid" ] && kill -0 "$(cat "$ESTADO/$nombre.pid")" 2>/dev/null; then
    echo "  $nombre ya estaba activo"; return; fi
  if command -v setsid >/dev/null; then
    setsid nohup "$@" > "$ESTADO/logs/$nombre.log" 2>&1 < /dev/null &
  else
    nohup "$@" > "$ESTADO/logs/$nombre.log" 2>&1 < /dev/null &
  fi
  echo $! > "$ESTADO/$nombre.pid"
  echo "  $nombre iniciado (registro en entorno/estado/logs/$nombre.log)"
}

echo "Iniciando servicios..."
arrancar mlflow mlflow server --host 127.0.0.1 --port 5000 \
  --backend-store-uri "sqlite:///$ESTADO/mlflow.db" --artifacts-destination "$ESTADO/artefactos" "${SEGURIDAD[@]}"
arrancar airflow airflow standalone

echo "Esperando a MLflow..."
for _ in $(seq 60); do curl -s http://localhost:5000/health | grep -q OK && break; sleep 2; done
echo "Registrando los modelos de la sesion 3 (solo la primera vez)..."
python "$BASE/entorno/preparar_modelos.py"
echo "Esperando a Airflow (hasta 2 minutos la primera vez)..."
python "$BASE/entorno/verificar.py" --esperar
