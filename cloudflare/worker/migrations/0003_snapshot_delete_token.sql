ALTER TABLE snapshots
ADD COLUMN delete_token TEXT;

UPDATE snapshots
SET delete_token = lower(hex(randomblob(32)))
WHERE delete_token IS NULL OR delete_token = '';
