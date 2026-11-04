-- Local demo: latest 6 articles, three test users. Existing pairs are skipped.
-- Run from backend:
-- docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < generate/seed_demo_likes.sql
BEGIN;
LOCK TABLE public.article_likes, public.article_like_history IN SHARE ROW EXCLUSIVE MODE;

CREATE TEMP TABLE demo_like_targets ON COMMIT DROP AS
WITH articles AS (
    SELECT id, row_number() OVER (ORDER BY published_at DESC, id DESC) AS n
    FROM public.news_articles
    ORDER BY published_at DESC, id DESC
    LIMIT 6
), users(user_id, user_number) AS (
    VALUES ('demo_u001', 1), ('demo_u002', 2), ('demo_u003', 3)
)
SELECT u.user_id, a.id AS article_id,
       ((a.n + u.user_number) % 3 = 0) AS unlike_after
FROM articles a CROSS JOIN users u
WHERE NOT EXISTS (
    SELECT 1 FROM public.article_likes l
    WHERE l.user_id = u.user_id AND l.article_id = a.id
)
AND NOT EXISTS (
    SELECT 1 FROM public.article_like_history h
    WHERE h.user_id = u.user_id AND h.article_id = a.id
);

-- All target pairs liked one hour ago.
INSERT INTO public.article_like_history
    (change_id, user_id, article_id, action, changed_at)
SELECT gen_random_uuid(), user_id, article_id, 'like',
       CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM demo_like_targets;

-- Some pairs subsequently unliked 30 minutes ago.
INSERT INTO public.article_like_history
    (change_id, user_id, article_id, action, changed_at)
SELECT gen_random_uuid(), user_id, article_id, 'unlike',
       CURRENT_TIMESTAMP - INTERVAL '30 minutes'
FROM demo_like_targets WHERE unlike_after;

-- Store only the pairs whose final state is liked.
INSERT INTO public.article_likes (user_id, article_id, liked_at)
SELECT user_id, article_id, CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM demo_like_targets WHERE NOT unlike_after;

SELECT user_id, count(*) AS seeded_pairs,
       count(*) FILTER (WHERE NOT unlike_after) AS currently_liked,
       count(*) FILTER (WHERE unlike_after) AS subsequently_unliked
FROM demo_like_targets GROUP BY user_id ORDER BY user_id;
COMMIT;
