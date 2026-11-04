-- Existing DB: rename identity columns without deleting rows.
-- Stop the old WAS before applying; restart with reader_id code afterwards.
-- Re-running after migration is safe. Unexpected schemas abort the transaction.
BEGIN;
DO $$
DECLARE
    target text;
    has_old boolean;
    has_new boolean;
BEGIN
    FOREACH target IN ARRAY ARRAY['article_likes', 'article_like_history'] LOOP
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = target AND column_name = 'user_id'
        ) INTO has_old;
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = target AND column_name = 'reader_id'
        ) INTO has_new;
        IF has_old AND NOT has_new THEN
            EXECUTE format('ALTER TABLE public.%I RENAME COLUMN user_id TO reader_id', target);
        ELSIF NOT has_old AND has_new THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Unexpected identity columns in public.%', target;
        END IF;
    END LOOP;
END $$;
COMMIT;
