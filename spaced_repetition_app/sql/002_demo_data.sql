INSERT INTO users (email)
SELECT 'demo@example.com'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'demo@example.com');

WITH ins_user AS (
    SELECT id FROM users WHERE email = 'demo@example.com'
), deck_ins AS (
    INSERT INTO decks (user_id, name, description)
    SELECT id, 'Русский алфавит', 'Пример карточек' FROM ins_user
    ON CONFLICT DO NOTHING
    RETURNING id, user_id
)
SELECT add_note_with_card(u.id, COALESCE(d.id, (SELECT id FROM decks WHERE user_id = u.id LIMIT 1)),
                          data.front, data.back, data.tags)
FROM ins_user u
LEFT JOIN deck_ins d ON true,
LATERAL (
    VALUES
        ('А', 'Первая буква алфавита', ARRAY['буквы']::text[]),
        ('Б', 'Вторая буква алфавита', ARRAY['буквы']::text[]),
        ('В', 'Третья буква алфавита', ARRAY['буквы']::text[])
) AS data(front, back, tags)
WHERE NOT EXISTS (
    SELECT 1 FROM notes n
    WHERE n.user_id = u.id AND n.front = data.front AND n.back = data.back
);
