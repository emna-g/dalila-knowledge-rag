"""Applique les changements RELUS ET VALIDÉS des sources jusqu'à Dalila, avec les tests en barrière.

python -m dalila.sources.appliquer                    montre ce qui serait appliqué (rien n'est modifié)
python -m dalila.sources.appliquer --appliquer        applique
python -m dalila.sources.appliquer --appliquer --sans-vecteurs   sans recalcul des vecteurs (machine de test)

Pour chaque source validée (rafraichir --valider) dont la version validée n'est pas encore appliquée :
  1. ses passages dans donnees/corpus/passages.jsonl sont remplacés par le texte validé, découpé comme dans la
     fusion (decoupage.py) ; le corpus d'avant est sauvegardé dans donnees/corpus/sauvegardes/ ;
  2. charger (les passages dont le texte n'a pas changé gardent leurs vecteurs) -> vectoriser (seulement les passages
     nouveaux ou changés) -> construire_abox (le graphe n'est mis en service que s'il passe SHACL et ses requêtes) ;
  3. tests des outils de l'agent : s'ils échouent, le corpus d'avant est remis et rechargé ; rien n'est marqué appliqué.
Une source absente du corpus (citée seulement par db/reference/*.csv) n'a rien à remplacer : ces fichiers sont relus et
corrigés à la main ; la validation suffit. Un PDF scanné (sans texte) attend un OCR : il reste en attente, signalé.
"""
import argparse, datetime as dt, json, shutil, subprocess, sys
from dalila.config import DONNEES, RACINE
from dalila.sources.decoupage import contient_chiffre, decouper, langue, paragraphes
from dalila.sources.rafraichir import Etat, cle, maintenant

CORPUS = DONNEES / "corpus" / "passages.jsonl"
ETAPES = [("charger", ["-m", "dalila.connaissances.charger"]),
          ("vectoriser", ["-m", "dalila.connaissances.vectoriser"]),
          ("construire_abox", ["-m", "dalila.connaissances.construire_abox"]),
          ("tests des outils", ["-m", "tests.traitement.test_outils"])]


def en_attente(etat):
    """URL validées (pas « à relire ») dont la version validée n'est pas celle appliquée."""
    return sorted(u for u, e in etat.sources.items()
                  if e.get("empreinte_validee") and not e.get("a_relire")
                  and e.get("empreinte_validee") != e.get("empreinte_appliquee"))


def nouveaux_passages(url, texte, modele, quand):
    """Passages du texte validé, avec les métadonnées des passages qu'ils remplacent (type, titre, zone)."""
    base = cle(url)[:8]
    corps = texte if "=== page " in texte else paragraphes(texte)
    passages = []
    for i, (page, article, t) in enumerate(decouper(corps)):
        if i > 999:
            raise ValueError(f"plus de 1000 passages pour {url}")
        passages.append({"id": f"s{base}{i:03d}", "type": modele.get("type"), "titre": modele.get("titre"),
                         "texte": t, "source_url": url, "date_source": quand[:10], "langue": langue(t),
                         "zone_id": modele.get("zone_id"), "page": page, "article": article, "texte_ocr": False,
                         "pertinence": "principale", "raison_secondaire": None,
                         "contient_chiffre": contient_chiffre(t)})
    return passages


def preparer(etat, passages, quand):
    """(nouveau corpus, plan) ; plan : [(url, action, détail)] ; action : remplacer, reference, attente."""
    plan, nouveau, remplaces = [], list(passages), {}
    for url in en_attente(etat):
        anciens = [p for p in passages if p.get("source_url") == url]
        texte = etat.texte(url, "valide")
        if not anciens:
            plan.append((url, "reference", "absente du corpus : fichiers db/reference relus à la main"))
        elif not texte:
            plan.append((url, "attente", "texte indisponible (PDF scanné : OCR à faire)"))
        else:
            nouveaux = nouveaux_passages(url, texte, anciens[0], quand)
            if not nouveaux:  # jamais retirer les passages d'une source sans texte exploitable pour les remplacer
                plan.append((url, "attente", "texte validé trop court pour faire un passage : rien n'est remplacé"))
                continue
            remplaces[url] = nouveaux
            plan.append((url, "remplacer", f"{len(anciens)} passages -> {len(nouveaux)}"))
    if remplaces:
        nouveau, mis = [], set()
        for p in passages:
            u = p.get("source_url")
            if u in remplaces:
                if u not in mis:  # les nouveaux passages prennent la place des anciens, dans l'ordre du corpus
                    nouveau += remplaces[u]
                    mis.add(u)
            else:
                nouveau.append(p)
        ids = [p["id"] for p in nouveau]
        if len(ids) != len(set(ids)):
            raise ValueError("identifiants de passages en double : rien n'est appliqué")
    return nouveau, plan


def ecrire_corpus(passages, chemin=CORPUS):
    tmp = chemin.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for p in passages:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    tmp.replace(chemin)


def lancer(etapes):
    """Lance les étapes dans l'ordre ; rend (nom de l'étape en échec, fin de sa sortie) ou (None, "")."""
    for nom, args in etapes:
        print(f"--- {nom}", flush=True)
        r = subprocess.run([sys.executable, *args], cwd=RACINE, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        print("\n".join(r.stdout.strip().splitlines()[-5:]))
        if r.returncode != 0:
            return nom, (r.stdout + r.stderr)[-3000:]
    return None, ""


def appliquer(etat, sans_vecteurs=False, corpus=CORPUS, etapes=None):
    quand = maintenant()
    passages = [json.loads(l) for l in open(corpus, encoding="utf-8")]
    nouveau, plan = preparer(etat, passages, quand)
    a_ecrire = any(a == "remplacer" for _, a, _ in plan)
    sauvegarde = None
    if a_ecrire:
        (corpus.parent / "sauvegardes").mkdir(exist_ok=True)
        nom, n = f"passages_{quand.replace(':', '').replace(' ', '_')}", 1
        sauvegarde = corpus.parent / "sauvegardes" / f"{nom}.jsonl"
        while sauvegarde.exists():  # jamais écraser une sauvegarde
            n += 1
            sauvegarde = corpus.parent / "sauvegardes" / f"{nom}_{n}.jsonl"
        shutil.copy2(corpus, sauvegarde)
        ecrire_corpus(nouveau, corpus)
        etapes = etapes if etapes is not None else [e for e in ETAPES if not (sans_vecteurs and e[0] == "vectoriser")]
        echec, sortie = lancer(etapes)
        if echec:
            shutil.copy2(sauvegarde, corpus)  # retour arrière : corpus d'avant, rechargé
            lancer([e for e in (etapes or []) if e[0] == "charger"])
            return plan, f"ÉCHEC à l'étape « {echec} » : corpus d'avant remis et rechargé, rien n'est appliqué.\n{sortie}"
    for url, action, detail in plan:
        if action in ("remplacer", "reference"):
            e = etat.sources[url]
            e.update(empreinte_appliquee=e["empreinte_validee"], applique_le=quand)
    etat.enregistrer()
    journal = etat.dossier / "journal_appliquer.jsonl"
    with open(journal, "a", encoding="utf-8") as fh:
        for url, action, detail in plan:
            fh.write(json.dumps({"le": quand, "url": url, "action": action, "detail": detail,
                                 "sauvegarde_corpus": str(sauvegarde) if sauvegarde else None},
                                ensure_ascii=False) + "\n")
    return plan, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appliquer", action="store_true", help="appliquer (sinon : seulement montrer)")
    ap.add_argument("--sans-vecteurs", action="store_true", help="ne pas lancer vectoriser (machine de test)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    etat = Etat()
    if not CORPUS.exists():
        raise SystemExit(f"corpus absent : {CORPUS} (voir README, « Corpus »)")
    if not a.appliquer:
        _, plan = preparer(etat, [json.loads(l) for l in open(CORPUS, encoding="utf-8")], maintenant())
        print(f"{len(plan)} source(s) validée(s) à appliquer" + (" :" if plan else "."))
        for url, action, detail in plan:
            print(f"  [{action}] {url} : {detail}")
        return
    plan, erreur = appliquer(etat, sans_vecteurs=a.sans_vecteurs)
    for url, action, detail in plan:
        print(f"  [{action}] {url} : {detail}")
    if erreur:
        print(erreur)
        sys.exit(1)
    print(f"appliqué : {sum(a != 'attente' for _, a, _ in plan)} source(s) ; en attente : "
          f"{sum(a == 'attente' for _, a, _ in plan)}")


if __name__ == "__main__":
    main()
