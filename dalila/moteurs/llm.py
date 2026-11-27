"""Modèle de langage local (Ollama), avec appels d'outils. Aucun service externe, aucune clé (BNF9).

    from dalila.moteurs.llm import discuter
    reponse = discuter(messages, outils=definitions())   # -> {"content": ..., "tool_calls": [...], "duree_s": ...}

Réglages (fichier .env) :
  DALILA_LLM            modèle Ollama (défaut : qwen3:4b-instruct ; choix mesuré : docs/decisions.md)
  DALILA_LLM_URL        adresse d'Ollama (défaut : http://127.0.0.1:11434)
  DALILA_LLM_CPU        1 : processeur seulement, comme le serveur de l'AFI (pour mesurer) ; 0 (défaut) : carte graphique si là
  DALILA_LLM_FILS       nombre de fils de calcul (défaut 8, comme le serveur de l'AFI)
Le mode « réflexion » des modèles Qwen3 est coupé : il allonge beaucoup les réponses sur processeur. La variante
« instruct » est celle qui le respecte (l'étiquette qwen3:4b désigne la variante « thinking », qui réfléchit toujours).
"""
import json, os, time, urllib.request

MODELE_LLM = os.environ.get("DALILA_LLM", "qwen3:4b-instruct")
URL = os.environ.get("DALILA_LLM_URL", "http://127.0.0.1:11434")


class ErreurMoteur(Exception):
    """Le moteur ne répond pas (arrêté, trop lent) : le harnais répond quand même, en texte (BNF4)."""


def discuter(messages, outils=None, modele=None, delai_s=60, temperature=0.0, jetons_max=400, arret_si_texte=False):
    """jetons_max : borne de ce que le modèle écrit (≈ 5 jetons/s sur le processeur du serveur de l'AFI).

    arret_si_texte : le modèle doit appeler un outil ; s'il commence à écrire du texte, la génération est arrêtée tout
    de suite (lecture en flux, connexion fermée) et le résultat porte "interrompu": True. Coût : une seconde environ,
    au lieu d'une réponse entière écrite sans données.
    Rend {content, tool_calls, duree_s, jetons_lus, jetons_ecrits, fin ("stop" ou "length"), interrompu}.
    """
    options = {"temperature": temperature, "num_ctx": 8192, "num_predict": jetons_max}
    if os.environ.get("DALILA_LLM_CPU", "0") == "1":
        options.update({"num_gpu": 0, "num_thread": int(os.environ.get("DALILA_LLM_FILS", "8"))})
    corps = {"model": modele or MODELE_LLM, "messages": messages, "stream": arret_si_texte, "think": False,
             "options": options, "keep_alive": "30m"}
    if outils:
        corps["tools"] = outils
    req = urllib.request.Request(URL + "/api/chat", data=json.dumps(corps).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    debut = time.time()
    contenu, appels, fin, interrompu = "", [], {}, False
    try:
        with urllib.request.urlopen(req, timeout=delai_s) as r:
            if not arret_si_texte:
                fin = json.loads(r.read().decode("utf-8"))
                m = fin.get("message", {})
                contenu, appels = m.get("content") or "", m.get("tool_calls") or []
            else:
                for ligne in r:
                    morceau = json.loads(ligne.decode("utf-8"))
                    m = morceau.get("message", {})
                    contenu += m.get("content") or ""
                    appels += m.get("tool_calls") or []
                    if contenu.strip() and not appels:
                        interrompu = True  # fermer la connexion arrête la génération dans Ollama
                        break
                    if morceau.get("done"):
                        fin = morceau
                        break
    except Exception as ex:  # noqa: BLE001
        raise ErreurMoteur(f"{type(ex).__name__}: {ex}") from ex
    return {"content": contenu, "duree_s": round(time.time() - debut, 2), "interrompu": interrompu,
            "tool_calls": [{"nom": c["function"]["name"], "arguments": c["function"].get("arguments") or {}}
                           for c in appels],
            "jetons_lus": fin.get("prompt_eval_count"), "jetons_ecrits": fin.get("eval_count"),
            "fin": fin.get("done_reason")}
