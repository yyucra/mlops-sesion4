#!/usr/bin/env bash
# Detiene MLflow, Airflow, la API y el contenedor del laboratorio. Los modelos registrados se conservan.
ESTADO="$(cd "$(dirname "$0")" && pwd)/estado"
BASE="$(dirname "$(dirname "$ESTADO")")"
echo "Deteniendo servicios..."
for nombre in airflow mlflow; do
  archivo="$ESTADO/$nombre.pid"
  [ -f "$archivo" ] || continue
  pid=$(cat "$archivo")
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
  for _ in $(seq 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
  kill -KILL -- "-$pid" 2>/dev/null
  rm -f "$archivo"
  echo "  $nombre detenido"
done
pkill -f "$BASE/.venv/bin/" 2>/dev/null && echo "  api detenida"
command -v docker >/dev/null && docker rm -f api-fuga >/dev/null 2>&1 && echo "  contenedor api-fuga detenido"
exit 0
