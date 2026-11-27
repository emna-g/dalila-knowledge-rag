# Module voix

Voix vers texte (le texte reconnu est affiché avant traitement) et texte vers voix ; tout en local, sur processeur.

| | |
|---|---|
| **Exigences** | BF7, BF8, BNF3, BNF7, BNF8 (BF9 et BF13 : interface) |
| **Reconnaissance** | `reconnaissance.py` : faster-whisper `small` (MIT), int8, 8 fils ; noms des gouvernorats favorisés (hotwords) ; audio décodé en mémoire, jamais écrit ni gardé. |
| **Synthèse** | `synthese.py` : Piper (MIT), voix fr, en, de, tr, ar (`modeles/piper/`) ; balises lues par leur libellé, liens retirés, unités dites en mots ; dialectes en lettres arabes lus par la voix arabe ; arabizi : pas de voix (le texte reste). |
| **API** | `POST /carte/voix/transcrire` (fichier `audio`, `lang`) ; `POST /carte/voix/lire` (`texte`, `lang`) -> WAV, ou 204. |
| **Mesures** | `python -m eval.voix_bench` -> `eval/reports/voix_resume.json` ; tests : `python -m tests.voix.test_voix`. |
| **État** | Fait pour 5 langues (reconnaissance ≈ 3 s) ; dialectes maghrébins : voir docs/decisions.md (modèles spécialisés à mesurer). |

Installer les modèles (une fois, ~1 Go) :
```
.venv\Scripts\python -m piper.download_voices --data-dir modeles/piper fr_FR-siwis-medium en_US-lessac-medium de_DE-thorsten-medium tr_TR-dfki-medium ar_JO-kareem-medium
```
Whisper `small` est téléchargé au premier appel dans `modeles/whisper/`.
