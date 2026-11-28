"""Prépare tout ce dont le service a besoin, dans les volumes Docker ; chaque étape est sautée si elle est déjà faite.

    docker compose run --rm preparer        (lancé tout seul par « docker compose up » avant le service)

1. Base : tables, vues et comptes de Dalila (migrer) ; textes à citer (charger, si donnees/corpus/ est là) ; vecteurs
   manquants (vectoriser : aucun si la base vient de dalila_base.sql.gz, plusieurs heures sinon).
2. Graphe de connaissances (construire_abox) s'il n'existe pas encore, ou avec --graphe (après un apprentissage).
3. Modèles locaux, téléchargés une fois : recherche (BGE-M3), voix (Whisper, Whisper tunisien, Piper), langue
   (CAMeL MADAR-26 et le classifieur des lettres latines), noms de personnes (anonymisation).
"""
import shutil, subprocess, sys, time
from dalila.config import DONNEES, GRAPHE, MODELES, db

VOIX = ["fr_FR-siwis-medium", "en_US-ljspeech-medium", "de_DE-thorsten-medium", "tr_TR-dfki-medium",
        "ar_JO-kareem-medium"]


def etape(titre, *module):
    print(f"\n=== {titre}", flush=True)
    subprocess.run([sys.executable, "-m", *module], check=True)


def attendre_base():
    for _ in range(120):
        try:
            db("root").close()
            return
        except Exception:  # noqa: BLE001
            time.sleep(5)
    sys.exit("la base ne répond pas")


def compter(sql):
    try:
        con = db("root")
        with con.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchone().values())[0]
    except Exception:  # noqa: BLE001
        return 0
    finally:
        con.close()


def main():
    attendre_base()
    etape("tables, vues et comptes de Dalila", "dalila.connaissances.migrer")
    if (DONNEES / "corpus" / "passages.jsonl").exists():
        etape("textes à citer (les vecteurs des textes inchangés sont gardés)", "dalila.connaissances.charger")
    elif not compter("SELECT COUNT(*) FROM dalila_passages"):
        sys.exit("aucun texte à citer : mettre dalila_base.sql.gz dans donnees/ "
                 "(voir docs/docker.md)")
    if compter("SELECT COUNT(*) FROM dalila_passages WHERE embedding_bge IS NULL"):
        etape("vecteurs manquants (long sur processeur)", "dalila.connaissances.vectoriser")
    if "--graphe" in sys.argv or not (GRAPHE / "store").exists():
        etape("graphe de connaissances", "dalila.connaissances.construire_abox")

    print("\n=== modèles locaux", flush=True)
    manquantes = [v for v in VOIX if not (MODELES / "piper" / f"{v}.onnx").exists()]
    if manquantes:
        subprocess.run([sys.executable, "-m", "piper.download_voices", "--data-dir", str(MODELES / "piper"),
                        *manquantes], check=True)
    if not (MODELES / "langue_latin.joblib").exists():
        if not (DONNEES / "langue_latin.joblib").exists():
            sys.exit("détection de la langue absente : mettre langue_latin.joblib dans donnees/ (docs/docker.md)")
        shutil.copy(DONNEES / "langue_latin.joblib", MODELES / "langue_latin.joblib")  # le modèle mesuré, pas réentraîné
    from dalila.moteurs.embeddings import encoder_questions
    from dalila.langue.detection import detecter
    from dalila.harnais.garde_fous import anonymiser
    from dalila.voix import reconnaissance
    encoder_questions(["terrain industriel"])
    detecter("عندي مشروع")
    detecter("3andi projet")
    anonymiser("Mohamed Ben Salah à Sfax")
    reconnaissance.modele()
    reconnaissance.modele(reconnaissance.MODELE_ARABE)
    print("\nprêt", flush=True)


if __name__ == "__main__":
    main()
