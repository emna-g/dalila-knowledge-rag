# Image Python de Dalila : construction (ingest), évaluation et outils. torch CPU épinglé.
# Pour une carte graphique NVIDIA : utiliser l'index CUDA correspondant à la version PyTorch documentée et lancer avec --gpus all.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    HF_HOME=/models DALILA_MODELES=/models DALILA_DONNEES=/data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY dalila ./dalila
COPY ontology ./ontology
COPY db ./db
COPY eval ./eval

# Pas de secrets dans l'image : ils viennent du fichier .env au lancement.
CMD ["python", "-m", "eval.run_eval"]
