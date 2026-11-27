"""Le rafraîchissement de chaque semaine, en une commande (à planifier : scripts/rafraichir_sources.bat ou cron).

python -m dalila.sources.hebdo

  1. relit les sources dues de la liste fermée et enregistre leur état (rafraichir --enregistrer) ;
  2. recopie l'état dans agent_source_status (si la base répond ; sinon, signalé, la suite continue) ;
  3. applique les changements déjà relus et validés (appliquer --appliquer), tests en barrière.
Un changement nouveau n'est jamais appliqué sans relecture : il apparaît « à relire » dans le rapport ; après
relecture, « python -m dalila.sources.rafraichir --valider URL », et il sera appliqué au passage suivant (ou tout de
suite avec « python -m dalila.sources.appliquer --appliquer »).
Code de sortie : 0 si tout va bien, 1 si l'application a échoué (retour arrière fait), 2 s'il y a des alertes.
"""
import sys
from dalila.sources import appliquer as app
from dalila.sources.base import synchroniser
from dalila.sources.inventaire import sources_actives
from dalila.sources.rafraichir import DOSSIER, Etat, alertes, executer, maintenant, rapport


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    quand = maintenant()
    etat = Etat()
    resultats = executer(sources_actives(), etat, quand, sauver_tous=20)
    etat.enregistrer()
    texte = rapport(resultats, etat, quand, True)
    try:
        texte += f"\nÉtat recopié dans agent_source_status : {synchroniser(etat)} sources.\n"
    except Exception as ex:  # noqa: BLE001  (base arrêtée : la relecture reste faite et enregistrée)
        texte += f"\nATTENTION : état non recopié dans agent_source_status ({type(ex).__name__}: {ex}).\n"
    code = 0
    if app.CORPUS.exists():
        plan, erreur = app.appliquer(etat)
        if plan:
            texte += "\n## Application des changements validés\n\n" + \
                     "\n".join(f"- [{a}] {u} : {d}" for u, a, d in plan) + "\n"
        if erreur:
            texte += f"\n**{erreur.splitlines()[0]}**\n"
            code = 1
    else:
        texte += f"\nATTENTION : corpus absent ({app.CORPUS}) : rien n'est appliqué.\n"
    if code == 0 and alertes(resultats, etat):
        code = 2
    (DOSSIER / "rapports").mkdir(parents=True, exist_ok=True)
    f = DOSSIER / "rapports" / f"hebdo_{quand[:16].replace(':', '').replace(' ', '_')}.md"
    f.write_text(texte, encoding="utf-8")
    print(texte)
    print("rapport :", f)
    sys.exit(code)


if __name__ == "__main__":
    main()
