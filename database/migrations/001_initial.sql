\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE CHECK (email = lower(btrim(email)) AND email <> ''),
    display_name text NOT NULL CHECK (btrim(display_name) <> ''),
    password_hash text NOT NULL CHECK (password_hash <> ''),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE roles (
    id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE CHECK (name IN ('member', 'organizer', 'admin'))
);
INSERT INTO roles (name) VALUES ('member'), ('organizer'), ('admin');
CREATE TABLE user_roles (
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id smallint NOT NULL REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);
CREATE TABLE categories (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE CHECK (btrim(name) <> '')
);
CREATE TABLE member_preferences (
    user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    interests text[] NOT NULL DEFAULT '{}',
    chosen_area text,
    preferred_start date,
    preferred_end date,
    budget_max numeric(10,2) CHECK (budget_max >= 0),
    assistant_consent boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (preferred_end >= preferred_start)
);
CREATE TABLE events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizer_id bigint NOT NULL REFERENCES users(id),
    category_id bigint REFERENCES categories(id),
    title text NOT NULL CHECK (btrim(title) <> ''),
    description text NOT NULL DEFAULT '',
    location text NOT NULL CHECK (btrim(location) <> ''),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    timezone text NOT NULL DEFAULT 'Europe/Paris' CHECK (timezone = 'Europe/Paris'),
    capacity integer NOT NULL CHECK (capacity > 0),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at)
);
CREATE INDEX events_catalog_idx ON events (starts_at, category_id) WHERE status = 'published';
CREATE INDEX events_organizer_idx ON events (organizer_id);
CREATE TABLE reservations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_id bigint NOT NULL REFERENCES users(id),
    event_id bigint NOT NULL REFERENCES events(id),
    status text NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    reserved_at timestamptz NOT NULL DEFAULT now(),
    cancelled_at timestamptz,
    CHECK ((status = 'confirmed' AND cancelled_at IS NULL)
        OR (status = 'cancelled' AND cancelled_at IS NOT NULL AND cancelled_at >= reserved_at))
);
CREATE UNIQUE INDEX reservations_active_unique ON reservations (member_id, event_id) WHERE status = 'confirmed';
CREATE INDEX reservations_event_idx ON reservations (event_id, status);
CREATE TABLE faqs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question text NOT NULL,
    answer text NOT NULL,
    sort_order integer NOT NULL DEFAULT 0,
    published boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE legal_pages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('terms', 'legal_notice')),
    version integer NOT NULL CHECK (version > 0),
    content text NOT NULL,
    published_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, version)
);
CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER preferences_updated BEFORE UPDATE ON member_preferences FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER events_updated BEFORE UPDATE ON events FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER faqs_updated BEFORE UPDATE ON faqs FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER legal_updated BEFORE UPDATE ON legal_pages FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TABLE schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_migrations (version) VALUES ('001_initial');
COMMIT;
