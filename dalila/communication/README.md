# API de communication

Cette couche expose un contrat HTTP stable et délègue toute l'orchestration au
harnais existant. Elle ne contient ni logique métier, ni accès direct à
MariaDB, au graphe ou au moteur RAG.

## Contrat v1

`POST /api/v1/chat`

```json
{
  "message": "Je cherche un lot à Sfax",
  "history": [{"role": "user", "content": "Bonjour"}],
  "lang": "fr",
  "context": {"page": "carte", "zone_id": "930508", "lot_id": null, "favorites": []}
}
```

`message` est limité à 500 caractères et `history` à 20 messages
`user`/`assistant`. Les champs inconnus sont rejetés.

Il s'agit du nouveau contrat DALILA `/api/v1`, pas d'un alias rétrocompatible
de l'ancien endpoint `/carte/chatbot`. Confirmer le contrat cible avec le
consommateur avant toute intégration frontend ou AFI.

La réponse contient `request_id`, `status` (`answered`, `abstained` ou
`degraded`), `answer`, `sources`, `map_data` et `error`. Les sources sont
normalisées uniquement depuis les résultats réellement retournés par les
outils; les identifiants de passage restent distincts des URL. Les erreurs de
requête sont renvoyées en HTTP 422 et les erreurs internes en HTTP 500, avec un
code stable et un identifiant de requête.

`map_data` est réservé à une collection GeoJSON issue d'un outil de données
cartographiques. Il vaut actuellement `null` : aucun outil enregistré par
l'agent ne retourne de géométrie, et l'API n'en fabrique pas.

## Carte AFI SQL/KML

- `GET /api/v1/map/zones` retourne les zones visibles et leurs coordonnées
  ponctuelles depuis `v_pub_zones`.
- `GET /api/v1/map/zones/{zone_id}/lots` retourne les contours GeoJSON issus de
  `v_pub_lot_polygones`/`lots_kml`, avec pagination par `after_lot_id` et
  `limit` (1 à 1 000, défaut 500). Les contours non valides sont exclus et
  comptabilisés dans `rejected_geometry_count`.
- Chaque feature porte sa provenance et `availability_state: "unknown"`.
  L'endpoint ne publie pas un statut brut comme une disponibilité.

Ces routes ne fusionnent pas avec les observations AFIZI de l'ancienne
application. Les données cartographiques de cette API viennent exclusivement
des vues AFI SQL/KML.

## Architecture

- `schemas.py` définit les modèles d'échange et leurs limites.
- `api.py` porte les routes HTTP, CORS et la conversion des erreurs de transport.
- `service.py` adapte les DTO au retour de `Agent.repondre()`; l'agent demeure
  l'unique propriétaire de la boucle LLM/outils et des garde-fous.
- `traitement/carte.py` interroge en lecture seule les vues publiques AFI et
  convertit les contours KML en GeoJSON; il ne touche pas aux migrations.
- Les résultats bruts d'outils ne sont conservés que dans le retour interne de
  l'agent. L'API n'expose que les références de source et les champs explicitement
  prévus par son schéma.

Pour le développement local :

```powershell
python -m uvicorn dalila.communication.api:app --reload
```

La documentation OpenAPI est disponible sur `/docs`. Les origines CORS locales
par défaut sont `localhost:5173` et `127.0.0.1:5173`; elles peuvent être
remplacées par `DALILA_CORS_ORIGINS`, une liste séparée par des virgules.

Tests hors LLM et base réelle :

```powershell
py -3.12 -m unittest discover -s tests -p test_communication_api.py -v
```

## État

Le contrat chat et les routes de lecture cartographique sont implémentés. Leur
fonctionnement avec MariaDB réelle, l'index RAG et le LLM n'a pas été vérifié
dans les tests unitaires.
