ALTER TABLE users
  ADD COLUMN IF NOT EXISTS avatar_path text;

ALTER TABLE users
  DROP CONSTRAINT IF EXISTS users_avatar_path_check;

ALTER TABLE users
  ADD CONSTRAINT users_avatar_path_check
  CHECK (avatar_path IS NULL OR avatar_path ~ '^a[0-9]+-[a-f0-9]{16}\.webp$');

INSERT INTO schema_migrations (version) VALUES ('016_avatars');
