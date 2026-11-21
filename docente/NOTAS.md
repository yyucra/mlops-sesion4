# Sesión 4 · Notas para el docente

## Publicar el repositorio

1. Crear un repositorio **público** en GitHub, por ejemplo `mlops-sesion4`, y subir esta carpeta
   completa (incluye `.devcontainer/`, `.github/workflows/`, `.gitignore` y `.gitattributes`):

       cd mlops-sesion4
       git init -b main && git add . && git commit -m "Sesion 4"
       git remote add origin https://github.com/<usuario>/mlops-sesion4.git
       git push -u origin main

2. Abrir la pestaña **Actions** del repositorio y confirmar que el flujo `api-fuga` terminó en verde.
   En el laboratorio 2 los alumnos revisan esa ejecución. Para que tengan además una ejecución en
   rojo que comentar, se puede subir a una rama `demo-falla` el cambio que rompe el contrato
   (quitar `ge=0` de `antiguedad_meses` en `app/main.py`).
3. Publicar en el aula virtual la dirección del repositorio.
4. Probar una vez: **Code → Codespaces → Create codespace on main** y seguir la Parte 0 de la guía.

## Valores verificados (datos fijos y semilla 42)

| Elemento | Valor |
| --- | --- |
| v1 · profundidad 2, hoja 5 | S/ 41 400 en la evaluación de promoción |
| v2 · profundidad 4, hoja 43 · champion | S/ 47 340 |
| v3 · profundidad 4, hoja 37 · challenger | S/ 49 320 |
| Cliente de ejemplo (8 meses, S/ 95.5, 3 reclamos, sin contrato) | probabilidad 0.8776, ofrecer retención |
| Latencia local (100 consultas) | p95 de 2 a 4 ms |
| Canary al 20 %, 200 consultas (DAG o terminal) | 162 al campeón (24.1 % de ofertas) y 38 al retador (31.6 %) |
| Pruebas | 12 en verde; quitar `ge=0` hace fallar 1 |

## Modelo de referencia de las pruebas

`pruebas/modelo_referencia` es una copia local del campeón v2. Se regenera con
`python docente/crear_modelo_referencia.py` (con el entorno activo).

## Docker

En Codespaces, Docker viene con la configuración `.devcontainer`. En WSL se instala con
`sudo apt install -y docker.io` y `sudo usermod -aG docker $USER` (luego cerrar y abrir Ubuntu).
El contenedor usa `--network host` para llegar al MLflow del mismo equipo.

## Airflow en el laboratorio 2

El DAG `dags/liberacion_canary.py` orquesta la liberación: `pruebas` → `iniciar_canary` →
`enviar_consultas` → `evaluar_compuerta` → `decision_negocio` (HITLOperator: la persona responde en la
pestaña Required Actions de la tarea) → `aplicar_decision` → `promover` → `recargar_api` → `avisar_cd`,
o `revertir`. La API debe estar encendida; el DAG la controla con `POST /canary`, sin reiniciarla.

Caminos verificados: aprobar (champion pasa a v3 con `aprobado_por`), rechazar (retador al 0 %),
compuerta técnica que falla (latencia máxima 0.001 ms → revertir sin preguntar) y pruebas que fallan
(el DAG se detiene en `pruebas`).

Para que `avisar_cd` ejecute de verdad el flujo de GitHub Actions, se definen antes de
`bash entorno/iniciar.sh` las variables `GITHUB_TOKEN` (token con permiso sobre el repositorio) y
`GITHUB_REPO` (`usuario/mlops-sesion4`). Sin ellas, la tarea muestra el evento que enviaría.
