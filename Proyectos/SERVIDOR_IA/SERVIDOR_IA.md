# Plataforma universitaria de ciencia de datos estilo Kaggle (despliegue *on-premise*)

> **Estado:** documento de diseño corregido, listo para implementación por fases.
> **Fecha de revisión:** 2026-11-20.
> **Alcance:** propuesta para una universidad venezolana. **No** está pensada para ejecutarse en la máquina de este workspace (Celeron N4020, 3,6 GB RAM): la regla del repositorio es que el entrenamiento de modelos va siempre a Google Colab con TensorFlow.

---

## 0. Resumen ejecutivo y registro de correcciones

El diseño original era sólido en el fondo (soberanía de datos, open-source, resiliencia eléctrica), pero contenía cinco fallos que impedían el arranque, secretos embebidos en texto plano y varias inconsistencies entre secciones escritas en distintos turnos de conversación. Este documento los corrige y reordena el material en una especificación única.

| # | Problema del borrador | Resolución aplicada |
|---|---|---|
| 1 | El generador escribía en `datasets_out/` pero JupyterHub montaba `./datasets_ro/` | Un volumen con nombre `datasets`, montado en el Hub y en cada contenedor de estudiante |
| 2 | `"/srv/datasets"` en `DockerSpawner.volumes` se resolvía en el host Docker, no en el contenedor del Hub | Se usa el volumen con nombre `datasets` como clave del mapa |
| 3 | Regresión: `test.csv` con `id_registro`, ground truth y evaluador con `id_estudiante` | Una sola columna clave `id_registro` en los tres archivos, configurable vía `ID_COLUMN` |
| 4 | La configuración base del Hub no definía `bind_url` y Nginx enrutaba `/hub/` → 404 | `bind_url = http://0.0.0.0:8000/hub` en la configuración única del Hub |
| 5 | `sample_submission.csv` se describía pero ningún script lo generaba | Ambos generadores lo escriben |
| 6 | Secretos literales en Compose y código | Todo mediante variables `${VAR:?...}`, con `.env.example` y `.gitignore` |
| 7 | `docker.sock` en modo `rw` dentro del Hub | `tecnativa/docker-socket-proxy:3.4` con solo los endpoints necesarios |
| 8 | `team_name` libre → suplantación y evasión del límite diario | Identidad derivada del token de JupyterHub; modo abierta solo para pruebas aisladas |
| 9 | `admin_key` en query string | Header `X-Admin-Key` con `hmac.compare_digest` |
| 10 | Cálculo de nota con LLM y prosa | Funciones puras con tests; la escala 20→45 se invierte para RMSE |
| 11 | UPS sobreestimado (2,5–4 h) | Cálculo real: ≈1,1 kWh útiles → 1,1 h a 1 kW, 2,7 h a 400 W |
| 12 | `create_all()` al importar + `depends_on` sin healthcheck | Healthchecks y `condition: service_healthy`; migraciones explícitas |
| 13 | Culler cada 5 min pero documentado cada 10 | `--poll-interval=600`, `--max-age`, `--timeout=2700` |
| 14 | `kubespawner_override` en DockerSpawner | `c.DockerSpawner.profile_list` nativo |
| 15 | Volumen de backup atado al nombre de carpeta | `--volumes-from` + inventario antes de borrar |
| 16 | Documento escrito como transcripción de chat | Estructura de especificación; código separado de narrativa |

Las imágenes y paquetes se fijaron a versiones verificadas el 2026-11-20 (Docker Hub, GitHub Releases y PyPI). Se eliminaron los tags `latest`.

---

## 1. Contexto

### 1.1 Qué es Kaggle

Kaggle es una comunidad y plataforma de Google dedicada a la ciencia de datos, el aprendizaje automático y la IA. Ofrece cuatro cosas que esta propuesta debe reproducir, al menos en versión mínima:

1. **Datasets** accesibles y versionados.
2. **Notebooks** listos para usar, con aceleración por hardware cuando hace falta.
3. **Competiciones** con métrica inequívoca, envíos y *leaderboard* público/privado.
4. **Aprendizaje y comunidad**: microcursos, *notebooks* compartidos y discusión.

### 1.2 Traducción *on-premise*

| Capacidad Kaggle | Implementación propuesta | Estado en este diseño |
|---|---|---|
| Notebooks en la nube | JupyterHub + DockerSpawner | Completo |
| Motor de competiciones | FastAPI + PostgreSQL (evaluador propio) | Completo para tabular |
| Repositorio de datasets | MinIO + volumen `datasets` | Parcial: falta catálogo CKAN/DVC |
| Cursos y comunidad | Jupyter Book / Moodle + foros | **No implementado** (Fase 3) |
| Equipos reales | Usuarios de JupyterHub + token | Parcial: sin grupos persistentes |
| Registro de modelos | MLflow | **No implementado** (Fase 3) |

### 1.3 Supuestos y restricciones

- Red LAN/Wi-Fi universitaria; sin dependencia de Internet para operar.
- Presupuesto único estimado entre **USD 2 000 y 4 200**, sin mensualidades.
- 40–50 estudiantes concurrentes en el pico de laboratorio.
- Datos **100 % sintéticos** en la versión inicial. Si se sustituyen por registros reales (epidemiológicos, socioeconómicos), se requiere anonimización, política de retención y revisión ética **antes** de cargarlos.

---

## 2. Arquitectura

### 2.1 Topología

```
                       Red interna (intranet)
   Navegador ──:80──> Nginx ──┬── /            ──> eval-api (portal HTML)
                              ├── /api/        ──> eval-api (REST)
                              ├── /hub/        ──> JupyterHub :8000
                              │                     └── DockerSpawner ──> contenedores alumno
                              └── /minio/      ──> MinIO console :9001

   eval-api ──> PostgreSQL (envíos, cuotas, leaderboard)
   eval-api ──> /app/ground_truth (solo lectura, fuera del alcance del alumno)
   JupyterHub ──> docker-socket-proxy ──> Docker daemon (solo contenedores)
   Volumen `datasets` (ro) ──> todos los contenedores alumno
```

### 2.2 `docker-compose.yml`

```yaml
name: plataforma-datos-udo

services:
  reverse-proxy:
    image: nginx:1.30-alpine
    container_name: kaggle_udo_proxy
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      jupyterhub:
        condition: service_started
      minio:
        condition: service_healthy
      eval-api:
        condition: service_healthy
    networks: [kaggle_net]

  docker-socket-proxy:
    image: tecnativa/docker-socket-proxy:3.4
    container_name: kaggle_docker_proxy
    restart: unless-stopped
    environment:
      CONTAINERS: 1
      POST: 1
      START: 1
      STOP: 1
      DELETE: 1
      IMAGES: 1
      NETWORKS: 0
      VOLUMES: 0
      INFO: 0
      EVENTS: 0
      EXEC: 0
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks: [kaggle_net]

  jupyterhub:
    build: ./jupyterhub
    container_name: kaggle_jupyterhub
    restart: unless-stopped
    volumes:
      - jupyterhub_data:/srv/jupyterhub
      - datasets:/srv/datasets:ro
    environment:
      DOCKER_HOST: tcp://docker-socket-proxy:2375
      DOCKER_NETWORK_NAME: kaggle_net
      HUB_IP: jupyterhub
      JUPYTERHUB_CRYPT_KEY: ${JUPYTERHUB_CRYPT_KEY:?Definir en .env}
      JUPYTER_ADMIN_USER: ${JUPYTER_ADMIN_USER:-admin_docente}
      STUDENT_IMAGE: ${STUDENT_IMAGE:-jupyter/scipy-notebook:x86_64-python-3.11.6}
      STUDENT_MEM_LIMIT: ${STUDENT_MEM_LIMIT:-2G}
      STUDENT_MEM_GUARANTEE: ${STUDENT_MEM_GUARANTEE:-1G}
      STUDENT_CPU_LIMIT: ${STUDENT_CPU_LIMIT:-1.0}
      GPU_ALLOWED_USERS: ${GPU_ALLOWED_USERS:-}
    depends_on:
      docker-socket-proxy:
        condition: service_started
    networks: [kaggle_net]

  minio:
    image: minio/minio:RELEASE.2025-10-15T17-29-55Z
    container_name: kaggle_minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-admin_datos}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:?Definir en .env}
      MINIO_BROWSER_REDIRECT_URL: http://${SERVER_HOST}/minio/
      MINIO_SERVER_URL: http://${SERVER_HOST}/
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 10
    networks: [kaggle_net]

  postgres:
    image: postgres:16-alpine
    container_name: kaggle_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: kaggle_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Definir en .env}
      POSTGRES_DB: competiciones
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kaggle_user -d competiciones"]
      interval: 5s
      timeout: 3s
      retries: 15
    networks: [kaggle_net]

  eval-api:
    build: ./eval_engine
    container_name: kaggle_eval_engine
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://kaggle_user:${POSTGRES_PASSWORD:?Definir en .env}@postgres:5432/competiciones
      ADMIN_KEY: ${ADMIN_KEY:?Definir en .env}
      ID_COLUMN: ${ID_COLUMN:-id_estudiante}
      METRIC_TYPE: ${METRIC_TYPE:-auc}
      GROUND_TRUTH_PATH: /app/ground_truth/test_solution.csv
      GROUND_TRUTH_REG_PATH: /app/ground_truth_reg/test_solution.csv
      JUPYTERHUB_API_URL: http://jupyterhub:8000/hub/api
      SUBMISSION_IDENTITY_MODE: ${SUBMISSION_IDENTITY_MODE:-hub}
      LOCAL_TZ: America/Caracas
      MAX_DAILY_SUBMISSIONS: ${MAX_DAILY_SUBMISSIONS:-3}
    volumes:
      - ./ground_truth:/app/ground_truth:ro
      - ./ground_truth_reg:/app/ground_truth_reg:ro
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 10
    networks: [kaggle_net]

volumes:
  jupyterhub_data:
  minio_data:
  pg_data:
  datasets:

networks:
  kaggle_net:
    name: kaggle_net
    driver: bridge
```

**Notas sobre el Compose:**

- `datasets` es un volumen con nombre. Los CSV se generan en el host con `python3 generate_dataset.py` y se copian una vez con `docker compose cp ./datasets_out/. jupyterhub:/srv/datasets/` (y lo mismo para los archivos de `ground_truth`). El alumno lo ve en `/home/jovyan/datasets` en modo solo lectura.
- `SUBMISSION_IDENTITY_MODE=hub` exige el token del usuario de JupyterHub. El modo `open` solo debe usarse en un laboratorio aislado sin red externa.
- `SERVER_HOST` debe definirse en `.env` con la IP o el nombre DNS de la intranet.
- No se monta `docker.sock` en el Hub: se usa el proxy con `DOCKER_HOST=tcp://docker-socket-proxy:2375`.

### 2.3 `.env.example`

```bash
# Copiar a .env y rellenar. NINGUNO de estos valores debe versionarse.
SERVER_HOST=10.0.0.50

POSTGRES_PASSWORD=<generar: openssl rand -hex 24>
MINIO_ROOT_USER=admin_datos
MINIO_ROOT_PASSWORD=<generar: openssl rand -hex 24>
ADMIN_KEY=<generar: openssl rand -hex 24>
JUPYTERHUB_CRYPT_KEY=<generar: openssl rand -hex 32>
JUPYTER_ADMIN_USER=admin_docente

ID_COLUMN=id_registro
METRIC_TYPE=auc
MAX_DAILY_SUBMISSIONS=3
SUBMISSION_IDENTITY_MODE=hub
STUDENT_IMAGE=jupyter/scipy-notebook:x86_64-python-3.11.6
GPU_ALLOWED_USERS=admin_docente,tesista1
```

### 2.4 `.gitignore` del proyecto

```gitignore
.env
ground_truth/
ground_truth_reg/
datasets_out/
datasets_reg_out/
backups/
*.csv
!sample_submission.csv
```

`ground_truth/` y `ground_truth_reg/` son la llave de examen. Deben excluirse **desde el primer commit**, igual que los PDF de exámenes que se purgaron del historial de este repositorio con `git filter-repo`. Si se filtraron en algún momento, rotar el contenido y reescribir el historial.

### 2.5 Alineación de la configuración de JupyterHub con Nginx

Tres ajustes deben permanecer sincronizados:

| Archivo | Clave | Valor |
|---|---|---|
| `jupyterhub_config.py` | `c.JupyterHub.bind_url` | `http://0.0.0.0:8000/hub` |
| `jupyterhub_config.py` | `c.JupyterHub.hub_connect_url` | `http://jupyterhub:8000/hub` |
| `nginx.conf` | `location /hub/` | `proxy_pass http://jupyterhub_upstream/hub/;` + `X-Forwarded-Prefix: /hub` |

---

## 3. Hardware, costos y resiliencia eléctrica

### 3.1 Dimensionamiento para 50 estudiantes concurrentes

| Componente | Especificación | Justificación | Costo (USD) |
|---|---|---|---|
| CPU | AMD Ryzen 9 7900/7950X (12–16 núcleos, 24–32 hilos) | Preprocesamiento en Pandas y 50 contenedores | 420–550 |
| RAM | 128 GB DDR5 (4×32 GB) | 50×1 G garantizados + 2 G límite + SO/Postgres/MinIO | 380–450 |
| GPU (opcional) | RTX 3090 24 GB reacondicionada o RTX 4090 | *Deep learning*; **no** se particiona sola | 850–1 600 |
| Almacenamiento | NVMe 2 TB + HDD empresarial 4 TB | I/O de datasets y respaldos | 220–260 |
| Placa, case, fuente | B650/X670, flujo de aire alto, 1000 W 80+ Gold | Margen térmico y energético | 450–550 |
| Respaldo eléctrico | Inversor 2000 VA/1600 W + 2 baterías 100 Ah | Ver cálculo real abajo | 550–750 |
| **Total** | Nodo llave en mano | Sin mensualidades | **2 870–4 160** |

Sin GPU: **2 020–2 560 USD**, suficiente para el 100 % de las prácticas tabulares.

### 3.2 Cálculo honesto de autonomía

```
Energía nominal  = 2 baterías × 12 V × 100 Ah = 2,4 kWh
DoD recomendado  = 50 %                       → 1,2 kWh
Eficiencia inversor (90 %)                    → 1,08 kWh útiles
```

| Carga | Autonomía estimada |
|---|---|
| 1 000 W (CPU + GPU moderada) | ≈ 1,1 h |
| 600 W (CPU en pico) | ≈ 1,8 h |
| 400 W (laboratorio tabular) | ≈ 2,7 h |

La afirmación original de «2,5–4 h bajo carga media» solo se cumple sin GPU a plena carga. Además, **onda pura no equivale a UPS en línea**: para cortes reales y protección de PostgreSQL se requiere doble conversión (*online double-conversion*). Un inversor con transferencia de 10–20 ms puede reiniciar el servidor.

**Recomendación operativa:** apagado ordenado automático cuando queden 15 minutos de batería (script con `apcupsd` o `NUT`), además del respaldo en frío descrito en la sección 9.2.

### 3.3 Memoria y cuotas

Con `mem_limit=2G` y `mem_guarantee=1G`, 50 sesiones reservan 50 GB y pueden llegar a 100 GB, dejando 28 GB para el sistema. Es un diseño válido con 128 GB; si se baja a 64 GB, reducir la garantía a 512 M y el límite a 1,5 G.

Fijar además `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` y `MKL_NUM_THREADS=1` en el perfil del contenedor alumno: `n_jobs=-1` dentro de 1 vCPU lanza 24–32 hilos y produce *thrashing*.

---

## 4. Datathon inaugural

### 4.1 Diseño del reto

Para la primera edición se recomienda **un solo tipo de problema**: clasificación binaria sobre datos tabulares con **AUC-ROC**. Mezclar deserción (clasificación) y demanda eléctrica (regresión) en el mismo reto confunde la métrica y la rúbrica. El generador de regresión queda documentado como **reto número 2** (sección 7.3).

**Reto 1 — «Predicción de riesgo de deserción y rendimiento académico temprano».** Datos sintéticos, anonimizados, con contexto local reconocible (distancia al campus, carga académica, notas del primer corte).

### 4.2 Archivos entregados al estudiante

| Archivo | Contenido |
|---|---|
| `train.csv` | 70 % de los registros, con `id_registro`, predictoras y `target` |
| `test.csv` | 30 % restante, sin `target` |
| `sample_submission.csv` | Plantilla con `id_registro` y `prediccion` (0,5 en todas las filas) |
| `starter_notebook.ipynb` | Carga, validación cruzada, modelo base y envío en menos de 2 minutos |

Los cuatro los produce `generate_dataset.py`.

### 4.3 Reglas y mecánica

- **Partición:** 40 % público (score visible), 60 % privado (revelado al cierre). Ambas estratificadas por `target`.
- **Métrica:** AUC-ROC. F1 queda descartado porque el evaluador no lo implementa; si se requiere, se añade como función pura con tests, no como prosa.
- **Envíos:** máximo 3 por día por **usuario autenticado de JupyterHub**, en zona `America/Caracas` (no UTC: en Venezuela UTC−4 el reinicio UTC ocurre a las 20:00).
- **Identidad:** el evaluador valida el token del Hub contra `/hub/api/user`. El campo `team_name` del formulario es solo una etiqueta decorativa y **no** controla cuotas ni ranking.
- **Clasificación final:** cada equipo selecciona un **envío final** antes del cierre. El *private leaderboard* usa ese envío; si no lo selecciona, se usa su mejor score privado y se marca con aviso.

### 4.4 Cronograma (3 semanas)

| Semana | Actividad |
|---|---|
| 1 | Taller de 2 h: JupyterHub, EDA, primer envío con el *starter notebook* |
| 2 | Mentoría: nulos, *feature engineering*, validación cruzada estratificada |
| 3 | Congelamiento, revelación privada, defensa de 10 min de los 3 finalistas |

---

## 5. Motor evaluador (`eval_engine/`)

### 5.1 `requirements.txt`

```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-multipart==0.0.9
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
pandas==2.2.2
scikit-learn==1.5.1
httpx==0.27.2
```

### 5.2 `main.py`

```python
from datetime import datetime
from zoneinfo import ZoneInfo
import hmac
import io
import math
import os
from typing import Optional

import httpx
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sklearn.metrics import mean_squared_error, roc_auc_score
from sqlalchemy import (
    Column, DateTime, Float, Integer, String, UniqueConstraint,
    create_engine, func, select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_KEY = os.environ["ADMIN_KEY"]
ID_COLUMN = os.getenv("ID_COLUMN", "id_registro")
METRIC_TYPE = os.getenv("METRIC_TYPE", "auc").lower()
MAX_DAILY_SUBMISSIONS = int(os.getenv("MAX_DAILY_SUBMISSIONS", "3"))
HUB_API_URL = os.getenv("JUPYTERHUB_API_URL", "http://jupyterhub:8000/hub/api").rstrip("/")
IDENTITY_MODE = os.getenv("SUBMISSION_IDENTITY_MODE", "hub").lower()
LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "America/Caracas"))
GT_PATH = os.environ["GROUND_TRUTH_PATH"]
GT_REG_PATH = os.getenv("GROUND_TRUTH_REG_PATH", GT_PATH)

if METRIC_TYPE not in {"auc", "rmse"}:
    raise RuntimeError(f"METRIC_TYPE inválido: {METRIC_TYPE}")
if IDENTITY_MODE not in {"hub", "open"}:
    raise RuntimeError(f"SUBMISSION_IDENTITY_MODE inválido: {IDENTITY_MODE}")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    submitter = Column(String(100), nullable=False, index=True)
    team_label = Column(String(100), nullable=False)
    filename = Column(String(255), nullable=False)
    public_score = Column(Float, nullable=False)
    private_score = Column(Float, nullable=False)
    is_final = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)


class DailyQuota(Base):
    __tablename__ = "daily_quota"
    __table_args__ = (UniqueConstraint("submitter", "day", name="uq_submitter_day"),)

    submitter = Column(String(100), primary_key=True)
    day = Column(String(10), primary_key=True)  # YYYY-MM-DD en LOCAL_TZ
    count = Column(Integer, nullable=False, default=0)


# Las tablas se crean en el arranque controlado de la sección 9.1,
# NO al importar: el Compose espera a que PostgreSQL esté healthy.
def init_db() -> None:
    Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Motor de Evaluación - Plataforma de Datos Universitaria",
    version="2.0.0",
    on_startup=[init_db],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def resolve_identity(token: Optional[str], team_label: str) -> str:
    """Identidad del postulante. El modo 'open' es solo para laboratorio aislado."""
    if IDENTITY_MODE == "open":
        clean = (team_label or "").strip()
        if not clean:
            raise HTTPException(400, "El nombre del equipo es obligatorio en modo open.")
        return clean
    if not token:
        raise HTTPException(401, "Se requiere el token de JupyterHub (X-Hub-Token).")
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{HUB_API_URL}/user",
                headers={"Authorization": f"token {token}"},
            )
        resp.raise_for_status()
        name = resp.json().get("name", "")
    except Exception as exc:
        raise HTTPException(401, f"No se pudo validar el token de JupyterHub: {exc}")
    if not name:
        raise HTTPException(401, "El token de JupyterHub no devolvió un usuario.")
    return str(name)


def require_admin(x_admin_key: Optional[str]) -> None:
    if not x_admin_key or not hmac.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(403, "Acceso restringido al cierre del reto.")


def ground_truth(metric: str) -> pd.DataFrame:
    path = GT_REG_PATH if metric == "rmse" else GT_PATH
    if not os.path.exists(path):
        raise HTTPException(500, "Archivo de ground truth no encontrado en el servidor.")
    df = pd.read_csv(path)
    required = {ID_COLUMN, "target", "split"}
    if not required.issubset(df.columns):
        raise HTTPException(500, f"Ground truth debe contener: {sorted(required)}")
    if df[ID_COLUMN].duplicated().any():
        raise HTTPException(500, "El ground truth tiene IDs repetidos.")
    return df


def compute_score(y_true, y_pred, metric: str) -> float:
    """Función pura. Toda validación numérica vive aquí y es testeable sin red."""
    pred = pd.to_numeric(pd.Series(y_pred), errors="coerce").to_numpy(dtype=float)
    if pred.size == 0 or not np.isfinite(pred).all():
        raise HTTPException(400, "Las predicciones deben ser numéricas y finitas (sin NaN/Inf).")

    truth = pd.to_numeric(pd.Series(y_true), errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(truth).all():
        raise HTTPException(500, "El ground truth contiene valores no finitos.")

    if metric == "rmse":
        return float(mean_squared_error(truth, pred) ** 0.5)

    if np.any((pred < 0) | (pred > 1)):
        raise HTTPException(400, "Para AUC las predicciones deben ser probabilidades en [0, 1].")
    if len(np.unique(truth)) < 2:
        raise HTTPException(400, "La partición requiere ambas clases para AUC.")
    return float(roc_auc_score(truth, pred))


def consume_quota(db: Session, submitter: str) -> int:
    """Límite diario atómico. Reintentos acotados según el retry budget del repo."""
    day = now_local().strftime("%Y-%m-%d")
    for intento in range(3):
        try:
            quota = (
                db.query(DailyQuota)
                .filter(DailyQuota.submitter == submitter, DailyQuota.day == day)
                .with_for_update()
                .one_or_none()
            )
            if quota is None:
                quota = DailyQuota(submitter=submitter, day=day, count=0)
                db.add(quota)
                db.flush()
            if quota.count >= MAX_DAILY_SUBMISSIONS:
                db.rollback()
                raise HTTPException(
                    429,
                    f"Límite alcanzado: {MAX_DAILY_SUBMISSIONS} envíos por día "
                    f"({now_local().tzinfo}).",
                )
            quota.count += 1
            db.commit()
            return MAX_DAILY_SUBMISSIONS - quota.count
        except IntegrityError:
            db.rollback()
            if intento == 2:
                raise HTTPException(503, "No se pudo reservar la cuota; reintente.")
    raise HTTPException(503, "No se pudo reservar la cuota; reintente.")


@app.get("/health")
def health_check():
    return {"status": "ok", "metric": METRIC_TYPE, "identity_mode": IDENTITY_MODE}


@app.post("/submit")
async def submit_prediction(
    file: UploadFile = File(...),
    team_label: str = Form(""),
    x_hub_token: Optional[str] = Header(default=None, alias="X-Hub-Token"),
    db: Session = Depends(get_db),
):
    submitter = resolve_identity(x_hub_token, team_label)
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se admiten archivos .csv")

    content = await file.read(10 * 1024 * 1024)
    try:
        sub_df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(400, f"CSV inválido: {exc}")

    expected = {ID_COLUMN, "prediccion"}
    if not expected.issubset(sub_df.columns):
        raise HTTPException(400, f"El CSV debe contener las columnas: {sorted(expected)}")
    if sub_df[ID_COLUMN].duplicated().any():
        raise HTTPException(400, f"Hay IDs repetidos en la columna {ID_COLUMN}.")

    gt_df = ground_truth(METRIC_TYPE)
    merged = pd.merge(
        gt_df[[ID_COLUMN, "target", "split"]],
        sub_df[[ID_COLUMN, "prediccion"]],
        on=ID_COLUMN,
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(gt_df) or len(merged) != len(sub_df):
        raise HTTPException(
            400,
            f"IDs inconsistentes: ground_truth={len(gt_df)}, envío={len(sub_df)}, "
            f"coincidentes={len(merged)}.",
        )

    pub = merged[merged["split"] == "public"]
    priv = merged[merged["split"] == "private"]
    if pub.empty or priv.empty:
        raise HTTPException(500, "Una de las particiones está vacía; revisar estratificación.")

    pub_score = compute_score(pub["target"], pub["prediccion"], METRIC_TYPE)
    priv_score = compute_score(priv["target"], priv["prediccion"], METRIC_TYPE)
    remaining = consume_quota(db, submitter)

    record = Submission(
        submitter=submitter,
        team_label=(team_label or submitter).strip()[:100],
        filename=file.filename[:255],
        public_score=pub_score,
        private_score=priv_score,
        created_at=datetime.now(LOCAL_TZ),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "submission_id": record.id,
        "submitter": record.submitter,
        "metric": METRIC_TYPE,
        "public_score": round(pub_score, 6),
        "remaining_today": remaining,
    }


@app.post("/select-final/{submission_id}")
def select_final(
    submission_id: int,
    x_hub_token: Optional[str] = Header(default=None, alias="X-Hub-Token"),
    db: Session = Depends(get_db),
):
    submitter = resolve_identity(x_hub_token, "")
    record = db.get(Submission, submission_id)
    if record is None or record.submitter != submitter:
        raise HTTPException(404, "Envío no encontrado para este usuario.")
    db.query(Submission).filter(Submission.submitter == submitter).update({"is_final": 0})
    record.is_final = 1
    db.commit()
    return {"ok": True, "submission_id": submission_id}


def _agg(column, better):
    return func.min(column) if better == "min" else func.max(column)


def _order(column, better):
    return column.asc() if better == "min" else column.desc()


@app.get("/leaderboard/public")
def public_leaderboard(limit: int = 50, db: Session = Depends(get_db)):
    better = "min" if METRIC_TYPE == "rmse" else "max"
    best = _agg(Submission.public_score, better).label("best_score")
    subq = (
        db.query(Submission.submitter, best, func.count(Submission.id).label("total"))
        .group_by(Submission.submitter)
        .subquery()
    )
    rows = db.query(subq).order_by(_order(subq.c.best_score, better)).limit(limit).all()
    return {
        "metric": METRIC_TYPE,
        "leaderboard": [
            {
                "rank": i + 1,
                "team": r.submitter,
                "public_score": round(float(r.best_score), 6),
                "total_submissions": int(r.total),
            }
            for i, r in enumerate(rows)
        ],
    }


@app.get("/leaderboard/private")
def private_leaderboard(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)
    better = "min" if METRIC_TYPE == "rmse" else "max"

    final_scores = (
        db.query(Submission.submitter, Submission.private_score.label("score"))
        .filter(Submission.is_final == 1)
        .subquery()
    )
    fallback_scores = (
        db.query(
            Submission.submitter,
            _agg(Submission.private_score, better).label("score"),
        )
        .group_by(Submission.submitter)
        .subquery()
    )
    effective = func.coalesce(
        final_scores.c.score, fallback_scores.c.score
    ).label("effective_score")
    rows = (
        db.query(
            fallback_scores.c.submitter,
            effective,
            final_scores.c.score.label("final_score"),
        )
        .outerjoin(final_scores, final_scores.c.submitter == fallback_scores.c.submitter)
        .order_by(_order(effective, better))
        .all()
    )
    return {
        "metric": METRIC_TYPE,
        "private_leaderboard": [
            {
                "rank": i + 1,
                "team": r.submitter,
                "private_score": round(float(r.effective_score), 6),
                "final_submission_selected": r.final_score is not None,
            }
            for i, r in enumerate(rows)
        ],
    }
```

### 5.3 `eval_engine/Dockerfile`

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> Cambios frente al borrador: la identidad ya no es un campo libre; los IDs se validan con `validate="one_to_one"`; las predicciones se comprueban como finitas y, en AUC, dentro de `[0,1]`; la cuota diaria usa `SELECT … FOR UPDATE` en zona `America/Caracas`; el ranking privado usa el envío final; el Admin Key viaja en header; `create_all()` solo corre en el arranque controlado.

---

## 6. JupyterHub

### 6.1 `jupyterhub/Dockerfile`

```dockerfile
FROM jupyterhub/jupyterhub:6.2.0

RUN pip install --no-cache-dir \
    dockerspawner==14.0.0 \
    jupyterhub-idle-culler==2.0.0 \
    jupyterhub-nativeauthenticator==1.4.0 \
    docker==7.1.0

COPY jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
WORKDIR /srv/jupyterhub

CMD ["jupyterhub", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
```

### 6.2 `jupyterhub/jupyterhub_config.py` (configuración única)

No mantener dos configuraciones distintas: la versión base y la de NativeAuthenticator se fusionan aquí.

```python
import os
import sys

import nativeauthenticator

c = get_config()  # noqa

# --- Red y prefijo: debe coincidir con nginx.conf -------------------------
c.JupyterHub.bind_url = "http://0.0.0.0:8000/hub"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_url = "http://jupyterhub:8000/hub"
# JupyterHub genera su cookie_secret en jupyterhub_data si no se fija a mano.
# JUPYTERHUB_CRYPT_KEY se usa para cifrar los tokens en la base de datos.

# --- Autenticación ---------------------------------------------------------
c.JupyterHub.authenticator_class = "nativeauthenticator.NativeAuthenticator"
c.Authenticator.admin_users = {
    u.strip() for u in os.getenv("JUPYTER_ADMIN_USER", "admin_docente").split(",") if u.strip()
}
c.NativeAuthenticator.open_signup = True
c.NativeAuthenticator.minimum_password_length = 8
c.NativeAuthenticator.check_common_password = True
c.NativeAuthenticator.allowed_failed_logins = 5
c.NativeAuthenticator.seconds_before_next_try = 300
c.JupyterHub.template_paths = [nativeauthenticator.get_templates_path()]

# --- DockerSpawner a través del proxy de socket ----------------------------
network_name = os.getenv("DOCKER_NETWORK_NAME", "kaggle_net")
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.DockerSpawner.network_name = network_name
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.remove = True

# --- Cuotas: garantía menor que límite ------------------------------------
mem_limit = os.getenv("STUDENT_MEM_LIMIT", "2G")
mem_guarantee = os.getenv("STUDENT_MEM_GUARANTEE", "1G")
cpu_limit = float(os.getenv("STUDENT_CPU_LIMIT", "1.0"))
c.DockerSpawner.mem_limit = mem_limit
c.DockerSpawner.mem_guarantee = mem_guarantee
c.DockerSpawner.cpu_limit = cpu_limit

extra_env = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
c.DockerSpawner.environment = extra_env

# --- Volúmenes: nombre de volumen, NO ruta del host ------------------------
notebook_dir = "/home/jovyan/work"
c.DockerSpawner.notebook_dir = notebook_dir
c.DockerSpawner.volumes = {
    "jupyterhub-user-{username}": notebook_dir,
    "datasets": {"bind": "/home/jovyan/datasets", "mode": "ro"},
}

# --- Culler: 10 min de sondeo, 45 min de inactividad -----------------------
c.JupyterHub.services = [
    {
        "name": "idle-culler",
        "command": [
            sys.executable,
            "-m",
            "jupyterhub_idle_culler",
            "--timeout=2700",
            "--poll-interval=600",
            "--max-age=28800",
            "--remove-named-servers",
        ],
        "admin": True,
    }
]

# --- Perfiles CPU/GPU: API nativa de DockerSpawner -------------------------
from docker.types import DeviceRequest  # noqa: E402

gpu_allowed_users = {
    u.strip()
    for u in os.getenv("GPU_ALLOWED_USERS", "").split(",")
    if u.strip()
}
student_image = os.getenv(
    "STUDENT_IMAGE", "jupyter/scipy-notebook:x86_64-python-3.11.6"
)
gpu_image = os.getenv(
    "GPU_IMAGE", "jupyter/pytorch-notebook:x86_64-python-3.11.6"
)

profiles = [
    {
        "display_name": "CPU estándar (2 GB límite / 1 GB garantía / 1 vCPU)",
        "slug": "cpu-standard",
        "default": True,
        "image": student_image,
        "mem_limit": mem_limit,
        "mem_guarantee": mem_guarantee,
        "cpu_limit": cpu_limit,
    }
]

if gpu_allowed_users:
    profiles.append(
        {
            "display_name": "GPU NVIDIA (8 GB RAM / 4 vCPU / 1 GPU)",
            "slug": "gpu-shared",
            "image": gpu_image,
            "mem_limit": "8G",
            "mem_guarantee": "6G",
            "cpu_limit": 4.0,
            "device_requests": [DeviceRequest(count=1, capabilities=[["gpu"]])],
        }
    )

c.DockerSpawner.profile_list = profiles


def allowed_profiles(spawner):
    if spawner.user.name in gpu_allowed_users:
        return profiles
    return [p for p in profiles if p["slug"] == "cpu-standard"]


c.DockerSpawner.allowed_profiles = allowed_profiles
```

### 6.3 Sobre la GPU «compartida»

Una RTX 3090/4090 con `DeviceRequest(count=1)` se entrega **completa** a un contenedor; no hay particionado automático. Las opciones reales son:

1. **Exclusión por perfil** (la implementada): solo usuarios listados pueden pedirla; los demás nunca la ven.
2. **NVIDIA MPS** para tiempo compartido concurrente con aislamiento de memoria débil.
3. **MIG** solo en GPU de centro de datos (A100/H100), no en RTX.

No presentar la opción 1 como «GPU compartida» en la documentación de usuario: es **GPU reservada por perfil**.

---

## 7. Generadores de datos y cuaderno base

### 7.1 `generate_dataset.py` (reto 1)

```python
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ID_COLUMN = "id_registro"


def _split_private_public(df: pd.DataFrame, seed: int, stratify: bool):
    idx = df.index
    strat = df["target"] if stratify else None
    pub_idx, priv_idx = train_test_split(
        idx, test_size=0.60, random_state=seed, stratify=strat
    )
    splits = pd.Series(index=idx, dtype="object")
    splits.loc[pub_idx] = "public"
    splits.loc[priv_idx] = "private"
    return splits


def main(
    output_dir: str = "./datasets_out",
    gt_dir: str = "./ground_truth",
    n_samples: int = 4500,
    seed: int = 42,
):
    rng = np.random.default_rng(seed)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(gt_dir).mkdir(parents=True, exist_ok=True)

    ids = np.arange(100001, 100001 + n_samples)
    distancia_km = np.round(rng.gamma(shape=2.2, scale=4.5, size=n_samples), 2)
    horas_estudio_sem = np.round(
        rng.normal(loc=11.0, scale=4.5, size=n_samples).clip(1.0, 35.0), 1
    )
    asistencia_pct = np.round(rng.beta(a=5.0, b=1.8, size=n_samples) * 100.0, 1)
    promedio_corte1 = np.round(
        rng.normal(loc=12.2, scale=3.1, size=n_samples).clip(0.0, 20.0), 2
    )
    creditos_inscritos = rng.integers(9, 24, size=n_samples)
    tiene_beca_o_ayuda = rng.binomial(1, 0.35, size=n_samples)

    logit = (
        -4.2
        + 0.24 * promedio_corte1
        + 0.032 * asistencia_pct
        + 0.075 * horas_estudio_sem
        - 0.045 * distancia_km
        - 0.08 * np.maximum(0, creditos_inscritos - 18)
        + 0.45 * tiene_beca_o_ayuda
        + 0.012 * (promedio_corte1 - 10.0) * (asistencia_pct - 70.0) / 10.0
    )
    target = rng.binomial(1, 1.0 / (1.0 + np.exp(-logit)))

    df = pd.DataFrame(
        {
            ID_COLUMN: ids,
            "distancia_km": distancia_km,
            "horas_estudio_sem": horas_estudio_sem,
            "asistencia_pct": asistencia_pct,
            "promedio_corte1": promedio_corte1,
            "creditos_inscritos": creditos_inscritos,
            "tiene_beca_o_ayuda": tiene_beca_o_ayuda,
            "target": target,
        }
    )
    assert df[ID_COLUMN].is_unique, "Los IDs deben ser únicos"

    for col, rate in [("horas_estudio_sem", 0.04), ("distancia_km", 0.03)]:
        mask = rng.random(n_samples) < rate
        df.loc[mask, col] = np.nan

    train_df, test_full_df = train_test_split(
        df, test_size=0.30, random_state=seed, stratify=df["target"]
    )
    splits = _split_private_public(test_full_df, seed, stratify=True)
    for name in ("public", "private"):
        subset = test_full_df.loc[splits[splits == name].index, "target"]
        if subset.nunique() < 2:
            raise RuntimeError(f"La partición {name} no tiene ambas clases")

    test_features_df = test_full_df.drop(columns=["target"]).reset_index(drop=True)
    ground_truth_df = pd.DataFrame(
        {
            ID_COLUMN: test_full_df[ID_COLUMN].values,
            "target": test_full_df["target"].values,
            "split": splits.values,
        }
    )
    sample_submission = pd.DataFrame(
        {ID_COLUMN: test_features_df[ID_COLUMN], "prediccion": 0.5}
    )

    train_df.reset_index(drop=True).to_csv(Path(output_dir) / "train.csv", index=False)
    test_features_df.to_csv(Path(output_dir) / "test.csv", index=False)
    sample_submission.to_csv(
        Path(output_dir) / "sample_submission.csv", index=False
    )
    ground_truth_df.to_csv(Path(gt_dir) / "test_solution.csv", index=False)

    print(
        f"Generados {len(train_df)} train / {len(test_features_df)} test / "
        f"{len(sample_submission)} sample_submission"
    )
    print(
        "Distribución target en train:",
        train_df["target"].value_counts(normalize=True).round(3).to_dict(),
    )


if __name__ == "__main__":
    main()
```

### 7.2 `starter_notebook.ipynb`

Estructura JSON (los `source` van como listas de líneas):

```python
import os
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

DATA_DIR = "/home/jovyan/datasets"
ID_COLUMN = "id_registro"
train = pd.read_csv(f"{DATA_DIR}/train.csv")
test = pd.read_csv(f"{DATA_DIR}/test.csv")
print("Train:", train.shape, "Test:", test.shape)
```

```python
features = [c for c in train.columns if c not in (ID_COLUMN, "target")]
X, y = train[features], train["target"]

preprocessor = ColumnTransformer(
    [("num", SimpleImputer(strategy="median"), features)]
)
model = Pipeline(
    [
        ("prep", preprocessor),
        # n_jobs=1: el contenedor tiene 1 vCPU. n_jobs=-1 lanza todos los hilos
        # del host y degrada a los 49 compañeros.
        ("clf", RandomForestClassifier(
            n_estimators=200, random_state=42, n_jobs=1
        )),
    ]
)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
print(f"AUC-ROC CV (5-fold): {scores.mean():.5f} +/- {scores.std():.5f}")
```

```python
model.fit(X, y)
probs = model.predict_proba(test[features])[:, 1]
submission = pd.DataFrame({ID_COLUMN: test[ID_COLUMN], "prediccion": np.round(probs, 6)})
submission.to_csv("submission.csv", index=False)
submission.head()
```

```python
# La identidad la toma el servidor del token de JupyterHub; NO se envía team_name.
import os
import requests

token = os.environ["JUPYTERHUB_API_TOKEN"]
resp = requests.post(
    "http://eval-api:8000/submit",
    headers={"X-Hub-Token": token},
    files={"file": ("submission.csv", open("submission.csv", "rb"), "text/csv")},
    timeout=60,
)
print("Status:", resp.status_code)
print(resp.json())
```

### 7.3 `generate_regression_dataset.py` (reto 2)

```python
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ID_COLUMN = "id_registro"  # una sola clave, igual que el reto 1 y el evaluador


def main(
    output_dir: str = "./datasets_reg_out",
    gt_dir: str = "./ground_truth_reg",
    n_samples: int = 3600,
    seed: int = 2026,
):
    rng = np.random.default_rng(seed)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(gt_dir).mkdir(parents=True, exist_ok=True)

    ids = np.arange(500001, 500001 + n_samples)
    temperatura_c = np.round(
        rng.normal(loc=29.5, scale=3.2, size=n_samples).clip(20.0, 39.0), 1
    )
    humedad_pct = np.round(
        rng.normal(loc=74.0, scale=10.5, size=n_samples).clip(35.0, 98.0), 1
    )
    aulas_activas = rng.integers(2, 36, size=n_samples)
    dia_semana = rng.integers(0, 7, size=n_samples)
    es_fin_semana = (dia_semana >= 5).astype(int)
    hora_pico = rng.binomial(1, 0.35, size=n_samples)

    consumo_kwh = (
        140.0
        + 18.5 * np.maximum(0.0, temperatura_c - 25.0) ** 1.25
        + 0.85 * humedad_pct
        + 14.0 * aulas_activas
        - 65.0 * es_fin_semana
        + 55.0 * hora_pico
        + rng.normal(loc=0.0, scale=22.0, size=n_samples)
    )
    consumo_kwh = np.round(np.clip(consumo_kwh, 30.0, None), 2)

    df = pd.DataFrame(
        {
            ID_COLUMN: ids,
            "temperatura_c": temperatura_c,
            "humedad_pct": humedad_pct,
            "aulas_activas": aulas_activas,
            "dia_semana": dia_semana,
            "es_fin_semana": es_fin_semana,
            "hora_pico": hora_pico,
            "target": consumo_kwh,
        }
    )
    assert df[ID_COLUMN].is_unique
    for col, rate in [("temperatura_c", 0.03), ("humedad_pct", 0.04)]:
        mask = rng.random(n_samples) < rate
        df.loc[mask, col] = np.nan

    train_df, test_full_df = train_test_split(df, test_size=0.30, random_state=seed)
    # Estratificación aproximada por quintiles para evitar particiones vacías
    bins = pd.qcut(test_full_df["target"], q=5, labels=False, duplicates="drop")
    pub_idx, priv_idx = train_test_split(
        test_full_df.index, test_size=0.60, random_state=seed, stratify=bins
    )
    splits = pd.Series(index=test_full_df.index, dtype="object")
    splits.loc[pub_idx] = "public"
    splits.loc[priv_idx] = "private"

    test_features_df = test_full_df.drop(columns=["target"]).reset_index(drop=True)
    ground_truth_df = pd.DataFrame(
        {
            ID_COLUMN: test_full_df[ID_COLUMN].values,
            "target": test_full_df["target"].values,
            "split": splits.values,
        }
    )
    sample_submission = pd.DataFrame(
        {
            ID_COLUMN: test_features_df[ID_COLUMN],
            "prediccion": round(float(train_df["target"].mean()), 2),
        }
    )

    train_df.reset_index(drop=True).to_csv(Path(output_dir) / "train.csv", index=False)
    test_features_df.to_csv(Path(output_dir) / "test.csv", index=False)
    sample_submission.to_csv(Path(output_dir) / "sample_submission.csv", index=False)
    ground_truth_df.to_csv(Path(gt_dir) / "test_solution.csv", index=False)
    print(f"Regresión: {len(train_df)} train / {len(test_features_df)} test")


if __name__ == "__main__":
    main()
```

Para activar el reto 2, cambiar en `.env`:

```bash
METRIC_TYPE=rmse
ID_COLUMN=id_registro
```

y montar `ground_truth_reg` (ya incluido en el Compose). El evaluador ordena de menor a mayor RMSE.

---

## 8. Nginx y portal web

### 8.1 `nginx/nginx.conf`

```nginx
events {
    worker_connections 1024;
}

http {
    client_max_body_size 10M;   # un CSV de 4 500 filas no necesita 100 M

    map $http_upgrade $connection_upgrade {
        default upgrade;
        ''      close;
    }

    upstream jupyterhub_upstream { server jupyterhub:8000; }
    upstream eval_api_upstream   { server eval-api:8000; }
    upstream minio_console_upstream { server minio:9001; }

    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass http://eval_api_upstream/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /api/ {
            proxy_pass http://eval_api_upstream/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /hub/ {
            proxy_pass http://jupyterhub_upstream/hub/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Prefix /hub;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_read_timeout 86400s;
        }

        location /minio/ {
            rewrite ^/minio/(.*) /$1 break;
            proxy_pass http://minio_console_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
        }
    }
}
```

La consola de MinIO necesita además `MINIO_BROWSER_REDIRECT_URL` y `MINIO_SERVER_URL` en el Compose (ya incluidos). Verificar con un navegador que los enlaces de descarga no redirijan a `/`.

### 8.2 Portal HTML

El borrador usaba `innerHTML` con `row.team_name`, lo que permite **XSS almacenado**: un estudiante podía poner `<img onerror=...>` como nombre de equipo y ejecutar JavaScript en el navegador del docente. La versión corregida construye nodos con `textContent`.

Además, el envío desde el portal requiere el token de JupyterHub. El flujo recomendado es que el estudiante lo obtenga en `/hub/token` y lo pegue en el formulario; el *starter notebook* ya lo toma del entorno automáticamente.

```python
# Añadir a eval_engine/main.py
@app.get("/", response_class=HTMLResponse)
def web_portal():
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Leaderboard — Plataforma Universitaria de Datos</title>
  <style>
    body { font-family: system-ui, sans-serif; margin:0; background:#f4f6f9; color:#1f2937; }
    header { background:#0f172a; color:#fff; padding:1.25rem 2rem; }
    header a { color:#93c5fd; }
    .container { max-width:1000px; margin:2rem auto; padding:0 1rem;
                 display:grid; grid-template-columns:2fr 1fr; gap:1.5rem; }
    .card { background:#fff; border-radius:10px; padding:1.5rem;
            box-shadow:0 2px 8px rgba(0,0,0,.06); }
    table { width:100%; border-collapse:collapse; }
    th,td { text-align:left; padding:.6rem; border-bottom:1px solid #e5e7eb; }
    label { display:block; margin-top:.8rem; font-weight:600; }
    input { width:100%; margin-top:.3rem; padding:.5rem; box-sizing:border-box; }
    button { margin-top:1rem; background:#2563eb; color:#fff; border:0;
             padding:.7rem; border-radius:6px; cursor:pointer; }
    #msg { margin-top:1rem; white-space:pre-wrap; }
    .ok { color:#166534; } .err { color:#991b1b; }
  </style>
</head>
<body>
  <header><strong>Datathon Universitario</strong> ·
    <a href="/hub/">Ir a JupyterHub</a> ·
    <a href="/hub/token">Obtener token</a>
  </header>
  <div class="container">
    <div class="card">
      <h2>Public Leaderboard</h2>
      <table><thead><tr><th>#</th><th>Usuario</th><th>Puntaje</th><th>Envíos</th></tr></thead>
      <tbody id="lb-body"></tbody></table>
    </div>
    <div class="card">
      <h2>Enviar predicción</h2>
      <form id="sub-form">
        <label for="token">Token de JupyterHub</label>
        <input type="password" id="token" required />
        <label for="file">submission.csv</label>
        <input type="file" id="file" accept=".csv" required />
        <label for="team_label">Etiqueta de equipo (opcional)</label>
        <input type="text" id="team_label" />
        <button type="submit">Subir y evaluar</button>
      </form>
      <div id="msg"></div>
    </div>
  </div>
  <script>
    function cell(text) {
      const td = document.createElement('td');
      td.textContent = text;      // textContent, nunca innerHTML con datos del servidor
      return td;
    }
    async function loadLeaderboard() {
      const body = document.getElementById('lb-body');
      body.replaceChildren();
      try {
        const data = await (await fetch('/api/leaderboard/public')).json();
        (data.leaderboard || []).forEach(row => {
          const tr = document.createElement('tr');
          [row.rank, row.team, row.public_score, row.total_submissions]
            .forEach(v => tr.appendChild(cell(v)));
          body.appendChild(tr);
        });
      } catch (e) {
        body.appendChild(cell('Error al cargar el leaderboard.'));
      }
    }
    document.getElementById('sub-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = document.getElementById('msg');
      msg.textContent = '';
      const fd = new FormData();
      fd.append('file', document.getElementById('file').files[0]);
      fd.append('team_label', document.getElementById('team_label').value);
      try {
        const res = await fetch('/api/submit', {
          method: 'POST',
          headers: {'X-Hub-Token': document.getElementById('token').value},
          body: fd
        });
        const body = await res.json();
        msg.className = res.ok ? 'ok' : 'err';
        msg.textContent = res.ok
          ? `Envío #${body.submission_id} aceptado. ` +
            `Puntaje público (${body.metric.toUpperCase()}): ${body.public_score}\n` +
            `Envíos restantes hoy: ${body.remaining_today}`
          : (body.detail || 'Error al procesar el envío.');
        if (res.ok) loadLeaderboard();
      } catch (err) {
        msg.className = 'err';
        msg.textContent = 'Error de red al contactar el servidor.';
      }
    });
    loadLeaderboard();
  </script>
</body>
</html>"""
```

---

## 9. Operación

### 9.1 `manage_platform.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$PROJECT_DIR/backups}"
cd "$PROJECT_DIR"

start_platform() {
    mkdir -p "$BACKUP_ROOT"
    echo "[INFO] Construyendo y levantando contenedores Docker..."
    docker compose up -d --build

    echo "[INFO] Esperando a PostgreSQL y MinIO..."
    docker compose exec -T postgres pg_isready -U kaggle_user -d competiciones || true
    until docker compose exec -T postgres pg_isready -U kaggle_user -d competiciones >/dev/null 2>&1; do
        sleep 2
    done
    until docker compose exec -T minio mc ready local >/dev/null 2>&1; do
        sleep 2
    done

    echo "[INFO] Inicializando tablas del evaluador..."
    docker compose exec -T eval-api python -c "from main import init_db; init_db()"

    echo "[OK] Plataforma activa en http://${SERVER_HOST}/ y http://${SERVER_HOST}/hub/"
}

stop_platform() {
    docker compose down
    echo "[OK] Plataforma detenida."
}

backup_platform() {
    local timestamp dest
    timestamp="$(date +%Y%m%d_%H%M%S)"
    dest="$BACKUP_ROOT/backup_$timestamp"
    mkdir -p "$dest"
    chmod 700 "$dest"

    echo "[INFO] Respaldando PostgreSQL..."
    docker compose exec -T postgres \
        pg_dump -U kaggle_user competiciones | gzip > "$dest/postgres.sql.gz"

    echo "[INFO] Respaldando volúmenes por --volumes-from (independiente del nombre del proyecto)..."
    docker run --rm \
        --volumes-from kaggle_db \
        -v "$dest:/target" alpine:3.21 \
        tar -czf /target/pg_data.tar.gz -C /var/lib/postgresql/data .
    docker run --rm \
        --volumes-from kaggle_minio \
        -v "$dest:/target" alpine:3.21 \
        tar -czf /target/minio_data.tar.gz -C /data .

    echo "[INFO] Respaldando ground truth y configuración (material sensible)..."
    tar -czf - -C "$PROJECT_DIR" ground_truth ground_truth_reg nginx jupyterhub \
        | gzip > "$dest/config_and_gt.tar.gz"
    chmod 600 "$dest/config_and_gt.tar.gz"

    echo "[OK] Respaldo completado en: $dest"
}

case "${1:-}" in
    start)  start_platform  ;;
    stop)   stop_platform   ;;
    backup) backup_platform ;;
    *) echo "Uso: $0 {start|stop|backup}"; exit 3 ;;
esac
```

### 9.2 `daily_backup_job.sh` con barrera anti-borrado

```bash
#!/usr/bin/env bash
set -euo pipefail

PLATFORM_DIR="/srv/kaggle_platform"
BACKUP_ROOT="$PLATFORM_DIR/backups"
LOG_FILE="$BACKUP_ROOT/cron_backup.log"
RETENTION_DAYS=14
DRY_RUN="${DRY_RUN:-1}"   # 1 = solo inventario; 0 = borrar tras verificar

mkdir -p "$BACKUP_ROOT"
log() { echo "[$(date -Iseconds)] $*" >> "$LOG_FILE"; }

{
  log "Iniciando respaldo diario..."
  "$PLATFORM_DIR/manage_platform.sh" backup

  log "Inventario de respaldos con más de ${RETENTION_DAYS} días (DRY_RUN=$DRY_RUN):"
  root="$(realpath "$BACKUP_ROOT")"
  while IFS= read -r candidate; do
      target="$(realpath "$candidate")"
      # Cuatro barreras: mismo root, prefijo backup_, no symlink, no raíz
      case "$target" in
          "$root"/backup_*) ;;
          *) log "RECHAZADO (fuera del prefijo permitido): $target"; continue ;;
      esac
      [ -L "$candidate" ] && { log "RECHAZADO (symlink): $candidate"; continue; }
      log "CANDIDATO: $target"
      if [ "$DRY_RUN" = "0" ]; then
          rm -rf -- "$target"
          log "BORRADO: $target"
      fi
  done < <(find "$root" -maxdepth 1 -type d -name 'backup_*' -mtime "+$RETENTION_DAYS" -print)

  log "Proceso finalizado."
} >> "$LOG_FILE" 2>&1
```

```cron
0 2 * * * /srv/kaggle_platform/daily_backup_job.sh
```

La limpieza es **inventario primero, borrado después** y por defecto en modo seco, coherente con la barrera anti-borrado del repositorio. Nunca `sudo` dentro del script.

---

## 10. Rúbrica y cierre

### 10.1 Rúbrica (100 puntos)

| Criterio | Peso | Descripción |
|---|---|---|
| 1. Desempeño en *private leaderboard* | 45 | Escala lineal entre baseline docente (20) y mejor score privado (45). Para **RMSE la escala se invierte**: menor RMSE → mayor nota. |
| 2. Validación y prevención de *overfitting* | 20 | CV estratificada, nulos, variables con sentido; fugas de datos → 0–10 |
| 3. Reproducibilidad del *notebook* | 20 | Ejecución limpia arriba-abajo, semillas fijas, rutas relativas |
| 4. Explicabilidad y presentación | 15 | Defensa de 8–10 min: variables determinantes, intentos fallidos, limitaciones |

**Conversión determinista de la nota (función pura, sin LLM):**

```python
def nota_desempeno(score: float, baseline: float, best: float, metric: str) -> float:
    """20..45. En RMSE, 'best' es menor que 'baseline'; en AUC, es mayor."""
    if not all(map(lambda v: isinstance(v, (int, float)), (score, baseline, best))):
        raise TypeError("scores deben ser numéricos")
    denom = (baseline - best) if metric == "rmse" else (best - baseline)
    if denom <= 0:
        raise ValueError("El mejor score no mejora al baseline; revisar la escala")
    prop = (baseline - score) / denom if metric == "rmse" else (score - baseline) / denom
    return round(20.0 + 25.0 * min(1.0, max(0.0, prop)), 2)
```

### 10.2 Protocolo de cierre

1. **Congelamiento:** deshabilitar `/submit` y el formulario a la hora límite.
2. **Selección del envío final:** cada usuario llama a `POST /select-final/{id}` con su token antes del cierre.
3. **Revelación:** el docente consulta el ranking privado con el header, nunca con la clave en la URL:

```bash
curl -s -H "X-Admin-Key: $ADMIN_KEY" \
  "http://${SERVER_HOST}/api/leaderboard/private" | jq .
```

> El valor de `$ADMIN_KEY` se lee de `.env` en el servidor; no se escribe en el historial de comandos ni en logs de Nginx.

4. **Verificación:** comparar puesto público vs. privado (*shake-up*), ejecutar los *notebooks* finalistas en un contenedor limpio y aplicar la rúbrica.

---

## 11. Alineación con la arquitectura de 3 capas del workspace

Cada flujo repetible de esta propuesta debe aterrizar en las tres capas antes de considerarse terminado:

| Flujo | Capa 1 — Directiva | Capa 2 — Orquestación | Capa 3 — Ejecución |
|---|---|---|---|
| Generar datasets | `directives/generar_dataset_competencia.yaml` | `flujo_generar_dataset_competencia.py` | `execution/generar_dataset_competencia.py` |
| Evaluar envío | `directives/evaluar_envio_competencia.yaml` | `flujo_evaluar_envio.py` | `execution/evaluar_envio.py` |
| Publicar leaderboard | `directives/publicar_leaderboard.yaml` | `flujo_publicar_leaderboard.py` | `execution/publicar_leaderboard.py` |
| Respaldo | `directives/respaldar_plataforma.yaml` | `flujo_respaldar_plataforma.py` | `execution/respaldar_plataforma.py` |

El código incluido en este documento es la **referencia de comportamiento** de la capa 3. La decisión de qué métrica usar, cuántos envíos permitir y qué perfil de GPU se asigna sale de descriptores y variables de entorno, nunca de razonamiento en el chat.

---

## 12. Anexo: pruebas deterministas (sin red)

```python
# tests/test_evaluador.py
import math
import numpy as np
import pytest

from main import compute_score, nota_desempeno


def test_auc_perfecto():
    assert compute_score([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], "auc") == 1.0


def test_rmse_cero():
    assert compute_score([1, 2, 3], [1, 2, 3], "rmse") == pytest.approx(0.0)


def test_prediccion_no_finita_se_rechaza():
    with pytest.raises(Exception):
        compute_score([0, 1], [0.3, float("nan")], "auc")


def test_auc_fuera_de_rango_se_rechaza():
    with pytest.raises(Exception):
        compute_score([0, 1], [0.1, 1.4], "auc")


def test_auc_una_sola_clase_se_rechaza():
    with pytest.raises(Exception):
        compute_score([1, 1, 1], [0.2, 0.5, 0.9], "auc")


def test_escala_auc():
    assert nota_desempeno(0.90, 0.70, 0.95, "auc") == pytest.approx(20 + 25 * 0.8)


def test_escala_rmse_invertida():
    # 100 -> 60 es una mejora de 40 sobre un rango de 50 => 20 + 25*0.8 = 40
    assert nota_desempeno(60.0, 100.0, 50.0, "rmse") == pytest.approx(40.0)


def test_generadores_con_misma_semilla_son_identicos(tmp_path):
    # Verificar con hash de los CSV generados dos veces con seed=42
    import hashlib
    from generate_dataset import main as gen

    gen(str(tmp_path / "a"), str(tmp_path / "gta"), seed=42)
    gen(str(tmp_path / "b"), str(tmp_path / "gtb"), seed=42)
    for name in ("train.csv", "test.csv", "sample_submission.csv"):
        ha = hashlib.sha256((tmp_path / "a" / name).read_bytes()).hexdigest()
        hb = hashlib.sha256((tmp_path / "b" / name).read_bytes()).hexdigest()
        assert ha == hb, name
```

Los tests de integración con base de datos usan PostgreSQL efímero y comprueban: cuota 3 por día en zona `America/Caracas`, unicidad de `(submitter, day)`, orden ascendente para RMSE y descendente para AUC, y que un envío sin `is_final` no desplaza al final.

---

## 13. Guía rápida para estudiantes

1. **Entrar:** abrir `http://<IP_DEL_SERVIDOR>/hub/`, registrarse con usuario sin espacios y contraseña de al menos 8 caracteres. Si hay aprobación docente, avisar en clase.
2. **Ubicar los datos:** en `/home/jovyan/datasets` están `train.csv`, `test.csv` y `sample_submission.csv` (solo lectura). Copiar `starter_notebook.ipynb` a `/home/jovyan/work/` para editarlo.
3. **Entrenar y validar:** ejecutar arriba-abajo. Observar el AUC de validación cruzada. No depender solo del puntaje público.
4. **Enviar:** la última celda del cuaderno envía automáticamente con tu token de JupyterHub. También puedes usar el portal web, pegando el token de `/hub/token`.
5. **Límite:** 3 envíos por día por usuario, en hora local de Venezuela.
6. **Seleccionar envío final:** antes del cierre, marcar cuál envío representa tu trabajo final. El private leaderboard lo usará.
7. **Revisar posición:** el portal muestra el *Public Leaderboard* (40 %). El 60 % restante se revela al cierre.

---

## 14. Hoja de ruta y deuda conocida

| Fase | Entregable | Estado |
|---|---|---|
| 1 — Piloto | JupyterHub + datasets + evaluador AUC en una PC potente (20–30 alumnos) | Diseñado en este documento |
| 2 — Datathon | Primera competencia con datos sintéticos, portal y private leaderboard | Diseñado |
| 3 — Ecosistema | Catálogo CKAN/DVC, foros, Jupyter Book, MLflow, GPU con MPS | **No diseñado** |
| 4 — Datos reales | Sustitución por datos institucionales con anonimización y revisión ética | **Pendiente de gobernanza** |

**Deuda explicítamente reconocida:**

- MinIO hoy almacena artefactos pero no hay catálogo versionado; los «equipos» son usuarios, no grupos persistentes.
- No hay foros ni *code sharing*: para parecerse de verdad a Kaggle faltan esas piezas.
- La consola de MinIO en subruta y el prefijo `/hub/` deben verificarse con un navegador real tras el primer despliegue.
- El soporte de `DeviceRequest` depende de la versión instalada de DockerSpawner; verificar con `dockerspawner==14.0.0` antes de prometer GPU a los tesistas.
- Como alternativa de Fase 1, **Kaggle In Class** permite arrancar sin infraestructura, con el coste de depender de Internet y ceder soberanía de datos.
