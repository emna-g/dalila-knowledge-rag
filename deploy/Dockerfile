# Image de Dalila : l'API, l'interface de la carte et les outils (construction, évaluation, tests). Processeur seul,
# comme le serveur de l'AFI. Construite et lancée par docker-compose.yml (racine du dépôt) : docker compose up --build

# ---- 1. interface (frontend/app -> dist/)
FROM node:24-slim AS interface
WORKDIR /app
COPY frontend/app/package.json frontend/app/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/app/ ./
RUN npm run build

# ---- 2. service Python
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    DALILA_MODELES=/models HF_HOME=/models DALILA_DONNEES=/data DALILA_GRAPHE=/graphe DALILA_LLM_CPU=1

# libgomp1 : calcul parallèle de torch, ctranslate2 (Whisper) et onnxruntime (Piper)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY dalila ./dalila
COPY ontology ./ontology
COPY db ./db
COPY ajustement ./ajustement
COPY eval ./eval
COPY tests ./tests
COPY scripts ./scripts
COPY deploy/preparer.py ./deploy/preparer.py
COPY frontend/serveur.py ./frontend/serveur.py
COPY frontend/public ./frontend/public
COPY --from=interface /app/dist ./frontend/app/dist

# Pas de secrets ni de données dans l'image : .env, donnees/ et les modèles arrivent au lancement (volumes).
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "frontend.serveur:app", "--host", "0.0.0.0", "--port", "8000"]
