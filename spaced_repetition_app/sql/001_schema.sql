CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    deck_id uuid NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    front text NOT NULL,
    back text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cards (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    deck_id uuid NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    note_id uuid NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS card_state (
    card_id uuid PRIMARY KEY REFERENCES cards(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ease_factor numeric(4,2) NOT NULL DEFAULT 2.50,
    interval_days integer NOT NULL DEFAULT 0,
    reps integer NOT NULL DEFAULT 0,
    lapses integer NOT NULL DEFAULT 0,
    due_at timestamptz NOT NULL DEFAULT now(),
    last_reviewed_at timestamptz,
    suspended boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id uuid NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quality smallint NOT NULL CHECK (quality BETWEEN 0 AND 5),
    interval_days integer NOT NULL,
    ease_factor numeric(4,2) NOT NULL,
    reviewed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tags (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id uuid NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id uuid NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_card_state_due ON card_state (user_id, due_at) WHERE suspended = false;
CREATE INDEX IF NOT EXISTS idx_reviews_user_date ON reviews (user_id, reviewed_at);

CREATE OR REPLACE FUNCTION update_note_timestamp() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notes_updated_at ON notes;
CREATE TRIGGER trg_notes_updated_at
    BEFORE UPDATE ON notes
    FOR EACH ROW
    EXECUTE FUNCTION update_note_timestamp();

CREATE OR REPLACE FUNCTION ensure_tag(p_name text) RETURNS uuid AS $$
DECLARE
    v_id uuid;
BEGIN
    SELECT id INTO v_id FROM tags WHERE lower(name) = lower(p_name);
    IF v_id IS NULL THEN
        INSERT INTO tags(id, name) VALUES (gen_random_uuid(), p_name) RETURNING id INTO v_id;
    END IF;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION add_note_with_card(
    p_user_id uuid,
    p_deck_id uuid,
    p_front text,
    p_back text,
    p_tags text[]
) RETURNS uuid AS $$
DECLARE
    v_note_id uuid;
    v_card_id uuid;
    v_tag_name text;
    v_tag_id uuid;
BEGIN
    INSERT INTO notes(user_id, deck_id, front, back)
    VALUES (p_user_id, p_deck_id, p_front, p_back)
    RETURNING id INTO v_note_id;

    INSERT INTO cards(user_id, deck_id, note_id)
    VALUES (p_user_id, p_deck_id, v_note_id)
    RETURNING id INTO v_card_id;

    INSERT INTO card_state(card_id, user_id)
    VALUES (v_card_id, p_user_id);

    IF p_tags IS NOT NULL THEN
        FOREACH v_tag_name IN ARRAY p_tags LOOP
            v_tag_name := trim(v_tag_name);
            IF v_tag_name <> '' THEN
                v_tag_id := ensure_tag(v_tag_name);
                INSERT INTO note_tags(note_id, tag_id)
                VALUES (v_note_id, v_tag_id)
                ON CONFLICT DO NOTHING;
            END IF;
        END LOOP;
    END IF;

    RETURN v_card_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION apply_sm2(
    p_user_id uuid,
    p_card_id uuid,
    p_quality smallint
) RETURNS void AS $$
DECLARE
    v_state card_state%ROWTYPE;
    v_interval integer;
    v_ease numeric(4,2);
    v_reps integer;
    v_lapses integer;
    v_now timestamptz := now();
BEGIN
    IF p_quality < 0 OR p_quality > 5 THEN
        RAISE EXCEPTION 'Quality should be between 0 and 5';
    END IF;

    SELECT * INTO v_state
    FROM card_state
    WHERE user_id = p_user_id AND card_id = p_card_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Card state not found for card %', p_card_id;
    END IF;

    v_ease := v_state.ease_factor;
    v_reps := v_state.reps;
    v_lapses := v_state.lapses;

    IF p_quality < 3 THEN
        v_reps := 0;
        v_lapses := v_lapses + 1;
        v_interval := 1;
        v_ease := GREATEST(1.30, v_ease - 0.20);
    ELSE
        v_reps := v_reps + 1;
        IF v_state.reps = 0 THEN
            v_interval := 1;
        ELSIF v_state.reps = 1 THEN
            v_interval := 6;
        ELSE
            v_interval := CEIL(v_state.interval_days * v_ease);
        END IF;
        v_ease := GREATEST(1.30, v_ease + (0.1 - (5 - p_quality) * (0.08 + (5 - p_quality) * 0.02)));
    END IF;

    UPDATE card_state
    SET ease_factor = v_ease,
        interval_days = v_interval,
        reps = v_reps,
        lapses = v_lapses,
        due_at = v_now + make_interval(days => v_interval),
        last_reviewed_at = v_now,
        suspended = false
    WHERE card_id = p_card_id AND user_id = p_user_id;

    INSERT INTO reviews(card_id, user_id, quality, interval_days, ease_factor, reviewed_at)
    VALUES (p_card_id, p_user_id, p_quality, v_interval, v_ease, v_now);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW v_due_queue AS
SELECT
    cs.user_id,
    c.id AS card_id,
    c.deck_id,
    n.id AS note_id,
    n.front,
    n.back,
    cs.due_at,
    d.name AS deck_name,
    cs.suspended
FROM card_state cs
JOIN cards c ON c.id = cs.card_id
JOIN notes n ON n.id = c.note_id
JOIN decks d ON d.id = c.deck_id
WHERE cs.suspended = false;

CREATE OR REPLACE VIEW v_daily_stats AS
SELECT
    r.user_id,
    (date_trunc('day', r.reviewed_at))::date AS day,
    COUNT(*) AS reviews_count,
    AVG(CASE WHEN r.quality >= 3 THEN 1.0 ELSE 0.0 END) AS success_rate
FROM reviews r
GROUP BY r.user_id, (date_trunc('day', r.reviewed_at))::date;

CREATE OR REPLACE VIEW v_deck_progress AS
SELECT
    d.user_id,
    d.id AS deck_id,
    d.name,
    COUNT(DISTINCT c.id) AS total_cards,
    COUNT(DISTINCT CASE WHEN cs.reps > 0 THEN c.id END) AS learned_cards,
    COUNT(DISTINCT CASE WHEN cs.due_at <= now() AND cs.suspended = false THEN c.id END) AS due_now
FROM decks d
LEFT JOIN cards c ON c.deck_id = d.id
LEFT JOIN card_state cs ON cs.card_id = c.id
GROUP BY d.user_id, d.id, d.name;
