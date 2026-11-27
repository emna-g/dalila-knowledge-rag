"""Modèle de langage local (Ollama), avec appels d'outils. Aucun service externe, aucune clé (BNF9).

    from dalila.moteurs.llm import discuter
    reponse = discuter(messages, outils=definitions())   # -> {"content": ..., "tool_calls": [...], "duree_s": ...}

Réglages (fichier .env) :
  DALILA_LLM            modèle Ollama (défaut : qwen3.5:4b)
  DALILA_LLM_URL        adresse d'Ollama (défaut : http://127.0.0.1:11434)
  DALILA_LLM_CPU        1 : processeur seulement, comme le serveur de l'AFI (pour mesurer) ; 0 (défaut) : carte graphique si là
  DALILA_LLM_FILS       nombre de fils de calcul (défaut 8, comme le serveur de l'AFI)
Le mode « réflexion » des modèles Qwen3 est coupé : il allonge beaucoup les réponses sur processeur.
"""
import json, os, time, urllib.request

from dalila.config import charger_env

charger_env()

MODELE_LLM = os.environ.get("DALILA_LLM", "qwen3.5:4b")
URL = os.environ.get("DALILA_LLM_URL", "http://127.0.0.1:11434")


class ErreurMoteur(Exception):
    """Le moteur ne répond pas (arrêté, trop lent) : le harnais répond quand même, en texte (BNF4)."""


def discuter(messages, outils=None, modele=None, delai_s=60, temperature=0.0):
    options = {"temperature": temperature, "num_ctx": 8192}
    if os.environ.get("DALILA_LLM_CPU", "0") == "1":
        options.update({"num_gpu": 0, "num_thread": int(os.environ.get("DALILA_LLM_FILS", "8"))})
    corps = {"model": modele or MODELE_LLM, "messages": messages, "stream": False, "think": False,
             "options": options, "keep_alive": "30m"}
    if outils:
        corps["tools"] = outils
    req = urllib.request.Request(URL + "/api/chat", data=json.dumps(corps).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    debut = time.time()
    try:
        with urllib.request.urlopen(req, timeout=delai_s) as r:
            rep = json.loads(r.read().decode("utf-8"))
    except Exception as ex:  # noqa: BLE001
        raise ErreurMoteur(f"{type(ex).__name__}: {ex}") from ex
    m = rep.get("message", {})
    appels = [{"nom": c["function"]["name"], "arguments": c["function"].get("arguments") or {}}
              for c in m.get("tool_calls") or []]
    return {"content": m.get("content") or "", "tool_calls": appels, "duree_s": round(time.time() - debut, 2),
            "jetons_lus": rep.get("prompt_eval_count"), "jetons_ecrits": rep.get("eval_count")}
