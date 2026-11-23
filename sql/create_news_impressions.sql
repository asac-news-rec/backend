-- 기존 뉴스 DB에 기사별 피드 반환 기록 테이블을 추가합니다.
-- 새 DB나 DB 사용자를 만들지 않습니다.
-- IF NOT EXISTS는 기존 테이블의 컬럼과 제약조건을 변경하지 않습니다.

BEGIN;

CREATE TABLE IF NOT EXISTS public.news_impressions (
    impression_id UUID PRIMARY KEY,
    request_id UUID NOT NULL,
    reader_id TEXT NOT NULL,
    article_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    served_at TIMESTAMPTZ NOT NULL,
    score DOUBLE PRECISION,
    model_version TEXT,
    features_as_of TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS news_impressions_request_id_idx
    ON public.news_impressions (request_id);

CREATE INDEX IF NOT EXISTS news_impressions_served_at_idx
    ON public.news_impressions (served_at);

COMMENT ON TABLE public.news_impressions IS
    '피드 응답에 포함한 기사별 서버 반환 기록. 실제 브라우저 수신·화면 노출과 구분';
COMMENT ON COLUMN public.news_impressions.article_id IS
    '기사 삭제 후에도 이력을 보존하기 위해 외래 키를 설정하지 않은 기사 ID';
COMMENT ON COLUMN public.news_impressions.served_at IS
    '응답의 served_at과 동일한 서버 반환 시각. 저장·재시도 시각으로 대체하지 않음';
COMMENT ON COLUMN public.news_impressions.score IS
    '추천 점수. 추론 연동 전에는 NULL';
COMMENT ON COLUMN public.news_impressions.model_version IS
    '추천 모델 버전. 추론 연동 전에는 NULL';
COMMENT ON COLUMN public.news_impressions.features_as_of IS
    '추론 피처의 기준 시각. 추론 연동 전에는 NULL';

COMMIT;
