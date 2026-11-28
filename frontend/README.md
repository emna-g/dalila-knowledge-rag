# Interface

La carte interactive des zones industrielles de l'AFI (version 2.0) avec Dalila intégrée : recherche et filtres, fiche
complète de chaque zone, lots dessinés sur la carte avec leur état, vue satellite, comparateur de zones, conversation
en 6 langues avec la voix, arabe de droite à gauche. Pas de Laravel (docs/decisions.md, « Pile propre à l'équipe »).

| | |
|---|---|
| **Exigences** | BF5, BF7, BF9, BNF6, BNF7, BNF8 |
| **Contrat** | L'API de `dalila/communication` telle quelle (`/carte/chatbot`, `/carte/chatbot/avis`, `/carte/voix/transcrire`, `/carte/voix/lire`, `/sante`) + 4 lectures pour la carte dans `serveur.py`, par les vues publiques `v_pub_*` (compte `dalila_ro`). |
| **État** | Fait et essayé le 2026-11-27 sur la vraie base (50 zones, 2 524 lots) : bureau et téléphone, français / arabe / anglais. Reste : le back-office (agent de l'AFI, administrateur). |

## Lancer (aucun Node nécessaire : l'application construite est dans `app/dist/`)

```
.venv\Scripts\python -m uvicorn frontend.serveur:app --host 127.0.0.1 --port 8000
```
puis ouvrir **http://127.0.0.1:8000/**. Il faut : la base (`docker start dalila-db`) ; pour les réponses de Dalila,
Ollama avec `qwen3:4b-instruct` (sinon : réponse de secours avec le contact de l'AFI) ; pour la voix, les voix Piper
dans `modeles/piper/` (commande dans `dalila/voix/README.md`). Le micro du navigateur ne marche que sur
`http://127.0.0.1` / `localhost` ou en HTTPS.

## Modifier l'interface

```
cd frontend\app
npm install          (une fois)
npm run dev          http://localhost:5173 , rechargée à chaque changement ; l'API doit tourner sur le port 8000
npm run build        met à jour app/dist/ (à committer)
```
React 19, TypeScript, Vite, Tailwind CSS 4, MapLibre GL 6 (fond OpenFreeMap, satellite Esri), Framer Motion, Lucide.

## Ce que fait l'interface

| Partie | Fichier | Contenu |
|---|---|---|
| En-tête | `app/src/components/Entete.tsx` | Logo AFI, titre, enchères (filtre), comparer, langue FR / عربي / EN. |
| Recherche | `Recherche.tsx` | Chiffres clés, recherche (nom, gouvernorat, en arabe aussi), gouvernorat, lots disponibles, enchères ; filtres avancés : surface recherchée, prix maximum, développement régional, cahier des charges en ligne ; tri ; liste des zones. |
| Carte | `Carte.tsx` | Zones regroupées (nombre de lots disponibles), couleur selon l'état ; lots d'une zone dessinés (couleur + motif + mot dans la légende) ; lot choisi en jaune ; plan / satellite ; noms des lieux dans la langue de l'interface ; zones citées par Dalila qui pulsent. |
| Fiche de zone | `FicheZone.tsx` | Prix et prix après subvention, lots disponibles, surfaces ; onglets : aperçu (lots par état), lots (liste filtrable, fiche du lot avec prix du terrain), infrastructures (accès, réseaux, services proches), documents (cahiers des charges, plans). « Demander à Dalila » envoie la question avec la zone ou le lot en contexte. |
| Comparateur | `Comparateur.tsx` | 2 ou 3 zones côte à côte : prix, lots, surfaces, accès, réseaux ; le meilleur est signalé. |
| Dalila | `app/src/dalila/` | Mascotte et 3 cas d'usage à l'accueil ; réponses en fiches (`[[ZONE]]`, `[[LOT]]` → la carte s'y rend, `[[PDF]]` → document, `[[CHOIX]]` → boutons, sources) ; attente avec étapes et secondes ; micro avec consentement, texte reconnu vérifié avant l'envoi ; lecture à voix haute ; avis utile / pas utile ; 6 langues (fr, ar, tunisien, en, de, tr) ; contexte de la carte. |
| Données | `serveur.py` | `GET /carte/zones`, `/carte/zones/{id}` (fiche), `/carte/zones/{id}/lots` (contours), `/carte/lots/{id}`. |

La fenêtre de Dalila existe aussi seule (`public/dalila/dalila.js`, sans React), pour l'ajouter à la carte actuelle de
l'AFI ou à une page Laravel avec une ligne :
```html
<script src="https://dalila.exemple.tn/dalila/dalila.js" data-api="https://dalila.exemple.tn" data-lang="fr" defer></script>
```

## Limites

- La bande « J'ai compris » du concept board n'est pas faite : l'API ne renvoie pas encore ce que l'agent a compris.
- Fond de carte, imagerie satellite et polices viennent d'Internet ; sur un serveur sans Internet, il faudra les héberger.
- Textes de l'interface en dialecte : à faire relire par un locuteur.
