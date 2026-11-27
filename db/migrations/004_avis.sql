-- Avis du visiteur sur une réponse (contrat /carte/chatbot : utile / pas utile), rattaché au tour journalisé.
ALTER TABLE agent_turns ADD COLUMN IF NOT EXISTS avis TINYINT NULL;
ALTER TABLE agent_turns ADD COLUMN IF NOT EXISTS source VARCHAR(20) NULL;
