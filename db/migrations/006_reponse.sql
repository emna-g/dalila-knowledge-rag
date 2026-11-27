-- Phrases écrites par le modèle (anonymisées, sans le bloc de faits ajouté par le harnais) : pour faire de
-- l'entraînement à partir des conversations réussies (dalila/apprentissage/exporter.py).
ALTER TABLE agent_turns ADD COLUMN IF NOT EXISTS reponse TEXT NULL;
