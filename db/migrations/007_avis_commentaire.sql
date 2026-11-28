-- Commentaire facultatif avec l'avis (flux F06 du cahier des charges), anonymisé comme les questions.
ALTER TABLE agent_turns ADD COLUMN IF NOT EXISTS avis_commentaire VARCHAR(500) NULL;
