\set ON_ERROR_STOP on
BEGIN;
-- Icons stay aligned with app/seed_demo.py CATEGORIES.
ALTER TABLE categories ADD COLUMN icon text NOT NULL DEFAULT '✨';
ALTER TABLE categories ADD CONSTRAINT categories_icon_check
    CHECK (char_length(btrim(icon)) BETWEEN 1 AND 16);

ALTER TABLE events ADD COLUMN price_cents integer NOT NULL DEFAULT 0;
ALTER TABLE events ADD CONSTRAINT events_price_cents_check
    CHECK (price_cents >= 0 AND price_cents <= 500000);
ALTER TABLE events ADD COLUMN view_count integer NOT NULL DEFAULT 0;
ALTER TABLE events ADD CONSTRAINT events_view_count_check
    CHECK (view_count >= 0);

CREATE TABLE user_interests (
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id bigint NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, category_id)
);
CREATE INDEX user_interests_category_idx ON user_interests (category_id);

UPDATE categories AS c
SET icon = v.icon
FROM (VALUES
    ('Nature & plein air', '🌿'),
    ('Sport', '🏃'),
    ('Arts & culture', '🎨'),
    ('Jeux & rencontres', '🎲'),
    ('Cuisine', '🍳'),
    ('Musique', '🎵'),
    ('Photo & vidéo', '📸'),
    ('Bien-être', '🫧'),
    ('Langues & échanges', '💬'),
    ('Bénévolat', '🤝')
) AS v(name, icon)
WHERE c.name = v.name;

INSERT INTO categories (name, icon) VALUES
    ('Football', '⚽'),
    ('Pique-nique', '🧺'),
    ('Randonnée', '🥾'),
    ('Lecture', '📚'),
    ('Jeux vidéo', '🎮'),
    ('Yoga', '🧘'),
    ('Tech', '💻'),
    ('Théâtre', '🎭')
ON CONFLICT (name) DO UPDATE SET icon = EXCLUDED.icon;

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON user_interests TO joinly_app;
INSERT INTO schema_migrations (version) VALUES ('004_interests_pricing');
COMMIT;
