"""Ce que le harnais fait des résultats d'outils : une vue courte pour le modèle, et le bloc de faits ajouté à la réponse.

Sur le processeur du serveur de l'AFI, le modèle écrit 3 à 6 jetons par seconde (mesures : docs/decisions.md) : une
liste de lots recopiée coûte 30 à 60 s et un risque d'erreur de recopie. Les listes (lots, zones), les balises, les
documents et les sources sont donc écrits par le harnais, directement à partir des résultats d'outils : ils sont exacts
par construction. Le modèle n'écrit que les phrases qui répondent (BNF1, BNF2).

    vue("chercher_lots", resultat)   -> texte JSON court lu par le modèle (seulement ce qu'il lui faut pour répondre)
    bloc([(nom, resultat), ...])     -> lignes ajoutées sous la réponse du modèle (balises [[LOT]], [[ZONE]], [[PDF]]...)
"""
import json

TAILLE_VUE = 2000   # caractères d'un résultat rendus au modèle : chaque jeton lu coûte ~12 ms sur processeur
EXEMPLES = 5        # lignes d'une liste montrée au visiteur (le nombre exact est toujours donné à part)
SOURCES_MAX = 3


def sans_vides(v):
    """Retire les champs vides (None, listes et dicts vides) : rien à lire pour le modèle. Les zéros et les faux
    restent (ce sont des informations)."""
    if isinstance(v, dict):
        return {k: sans_vides(x) for k, x in v.items() if x is not None and x != [] and x != {}}
    if isinstance(v, list):
        return [sans_vides(x) for x in v]
    return v


def _couper(texte, n):
    texte = " ".join((texte or "").split())
    return texte if len(texte) <= n else texte[:n].rsplit(" ", 1)[0] + "…"


def _garder(d, cles):
    return {k: d[k] for k in cles if k in d}


def vue(nom, res):
    """Le résultat d'un outil tel que le modèle le lit : ce qu'il faut pour écrire la réponse, sans les listes longues,
    les liens et les sources (le harnais les ajoute lui-même sous la réponse)."""
    r = sans_vides(res)
    if r == {"resultat": None} or not r:
        r = {"resultat": "aucun résultat" + (" : nom de zone inconnu ou partagé par plusieurs zones ; pour un "
                                              "gouvernorat ou une région, utiliser lister_zones avec lieu"
                                              if nom == "fiche_zone" else "")}
    if "erreur" not in r:
        r.pop("sources", None)
        r.pop("filtres", None)
        if nom == "chercher_lots":
            r["lots"] = [_garder(l, ("zone", "surface_m2", "prix_m2_dt", "prix_total_dt", "prix_selon", "a_confirmer"))
                         for l in r.get("lots", [])[:3]]
        elif nom == "fiche_zone":
            for k in ("services_proches", "plans_de_lotissement", "cahiers_des_charges", "nom_ar"):
                r.pop(k, None)
        elif nom in ("lister_zones", "zones_proches"):
            r["zones"] = [_garder(z, ("nom", "gouvernorat", "lots_disponibles", "prix_m2_dt", "infrastructure", "km"))
                          for z in r.get("zones", [])[:EXEMPLES]]
        elif nom == "chercher_passages":
            r["passages"] = [{"titre": p.get("titre"), "texte": _couper(p.get("texte"), 400)}
                             for p in r.get("passages", [])[:3]]
        elif nom == "demarche":
            r["reponses_afi"] = [{"question": x.get("question"), "texte": _couper(x.get("texte"), n)}
                                 for x, n in zip(r.get("reponses_afi", []), (700, 300))]
            r["contact_afi"] = [_couper(x.get("texte"), 200) for x in r.get("contact_afi", [])]
        elif nom == "conseiller":  # l'essentiel : liens, documents et sources sont ajoutés par le harnais
            r = _garder(r, ("organisme_competent", "raison_organisme", "lieux_a_proposer", "note", "emplois"))                  | {"activite": (res.get("activites") or [{}])[0].get("libelle"),
                   "zones": [_garder(z, ("nom", "gouvernorat", "lots_adaptes", "prix_m2_dt", "prix_m2_subventionne_dt",
                                         "developpement_regional", "km")) for z in res.get("zones") or []],
                   "incitations": [i.get("titre") for i in (res.get("incitations") or [])[:2]],
                   "depot_de_la_demande": _couper(res.get("demarche_lieu_depot") or "", 160)}
            r = sans_vides(r)
    texte = json.dumps(r, ensure_ascii=False, separators=(",", ":"))
    return texte if len(texte) <= TAILLE_VUE else texte[:TAILLE_VUE] + "…(tronqué)"


def _n(x):
    """Nombre tel qu'il est dans la base, sans « .0 » ; groupé par milliers (lu comme un seul nombre par l'ancrage)."""
    if x is None:
        return None
    x = int(x) if float(x).is_integer() else x
    return f"{x:,}".replace(",", " ") if isinstance(x, int) else str(x)


def _lignes(nom, r):
    if nom == "chercher_lots":
        for l in r.get("lots", [])[:EXEMPLES]:
            prix = f" · {_n(l['prix_m2_dt'])} DT/m²" if l.get("prix_m2_dt") is not None else ""
            total = f" · {_n(l['prix_total_dt'])} DT" if l.get("prix_total_dt") is not None else ""
            yield f"- [[LOT:{l['lot_id']}:{l['numero']}]] {l['zone']} · {_n(l['surface_m2'])} m²{prix}{total}"
    elif nom in ("lister_zones", "zones_proches"):
        for z in r.get("zones", [])[:EXEMPLES]:
            km = f" · {z.get('infrastructure') or ''} {_n(z['km'])} km" if z.get("km") is not None else ""
            prix = f" · {_n(z['prix_m2_dt'])} DT/m²" if z.get("prix_m2_dt") is not None else ""
            yield f"- [[ZONE:{z['zone_id']}:{z['nom']}]] {z['gouvernorat']}{prix}{km}"
    elif nom == "fiche_zone" and r.get("zone_id"):
        yield f"[[ZONE:{r['zone_id']}:{r['nom']}]]"
        for d in (r.get("cahiers_des_charges") or []) + (r.get("plans_de_lotissement") or []):
            yield f"[[PDF:{d['lien']}:{d['titre']}]]"
    elif nom == "conseiller":
        for z in r.get("zones", []):
            prix = f" · {_n(z['prix_m2_dt'])} DT/m²" if z.get("prix_m2_dt") is not None else ""
            sub = f" (subventionné : {_n(z['prix_m2_subventionne_dt'])} DT/m²)" if z.get("prix_m2_subventionne_dt") else ""
            yield f"- [[ZONE:{z['zone_id']}:{z['nom']}]] {z['gouvernorat']} · {z['lots_adaptes']} lots{prix}{sub}"
        for z in r.get("zones", []):
            if z.get("cahier_des_charges"):
                yield f"[[PDF:{z['cahier_des_charges']}:Cahier des charges {z['nom']}]]"
        for i in r.get("incitations", [])[:2]:
            if i.get("lien"):
                yield f"[{i.get('titre') or 'Incitations'}]({i['lien']})"
    elif nom == "demarche":
        for s in r.get("services", []):
            yield f"[[CHOIX:{s['besoin']}]]"
    for p in r.get("lieux_a_proposer") or []:
        yield f"[[CHOIX:{p['nom']}]]"


def bloc(resultats):
    """Lignes ajoutées sous la réponse du modèle, à partir des résultats d'outils [(nom, résultat)] de la question."""
    lignes, liens = [], []
    for nom, r in resultats:
        if not isinstance(r, dict) or "erreur" in r:
            continue
        lignes += _lignes(nom, r)
        for s in r.get("sources") or []:
            if s.get("url") and s["url"] not in "".join(lignes):
                liens.append(f"[{s['titre']}]({s['url']})")
        for p in r.get("passages", [])[:SOURCES_MAX]:
            if p.get("lien"):
                liens.append(f"[{p['titre']}]({p['lien']})")
        for x in r.get("reponses_afi", [])[:1]:
            if x.get("lien"):
                liens.append(f"[{x.get('question') or 'AFI'}]({x['lien']})")
    lignes = list(dict.fromkeys(lignes))
    liens = list(dict.fromkeys(liens))[:SOURCES_MAX]
    return "\n".join(lignes + ([" · ".join(liens)] if liens else []))
