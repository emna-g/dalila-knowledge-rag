#!/bin/sh
# Ollama de Dalila : démarre le serveur, installe le modèle de l'agent une fois (volume), puis se déclare prêt.
# Le modèle de Dalila est le modèle ajusté : donnees/ajustement/modele/dalila.Q4_K_M.gguf (ajustement/Modelfile).
# Sans ce fichier, le service refuse de démarrer, sauf choix explicite du modèle de base (DALILA_LLM=qwen3:4b-instruct
# dans .env : autre comportement, mesuré dans docs/decisions.md).
ollama serve &
PID=$!
until ollama list >/dev/null 2>&1; do sleep 1; done
if [ -f /work/donnees/ajustement/modele/dalila.Q4_K_M.gguf ]; then
  ollama list | grep -q '^dalila-qwen3-4b' || (cd /work/ajustement && ollama create dalila-qwen3-4b -f Modelfile) || exit 1
elif [ "$DALILA_LLM" = "qwen3:4b-instruct" ]; then
  echo "modèle de base demandé (DALILA_LLM) : qwen3:4b-instruct"
  ollama list | grep -q '^qwen3:4b-instruct' || ollama pull qwen3:4b-instruct || exit 1
else
  echo "ERREUR : modèle de Dalila absent : mettre dalila.Q4_K_M.gguf dans donnees/ajustement/modele/ (docs/docker.md)" >&2
  exit 1
fi
touch /tmp/pret
wait $PID
