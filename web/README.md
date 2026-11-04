# 뉴스 API 연결 참고용 프론트

빌드 단계나 프론트 전용 컨테이너 없이 Nginx가 HTML/CSS/JavaScript를 제공합니다.
현재 피드는 최신순이며 개인 추천·인기순·행동 이벤트 로깅은 포함하지 않습니다.

## 실행

Docker Desktop을 켜고, backend 루트에서 실행합니다. 기존 PostgreSQL 테이블과 기사 적재가 필요합니다.

```bash
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 120
```

- 화면: http://localhost:8080/
- API 문서: http://localhost:8080/api/docs
- DB 연결 확인: http://localhost:8080/api/health

`web/index.html`을 파일로 직접 열지 말고 Nginx 주소로 접속하세요.
정적 파일 수정은 읽기 전용 bind mount에 반영되므로 브라우저 새로고침으로 확인합니다.
API 코드 수정은 이미지를 다시 빌드해야 합니다. Nginx 설정 수정은 `docker compose exec nginx nginx -t`로 검사하고 `docker compose restart nginx`로 적용합니다.

## 파일과 데이터 흐름

| 파일 | 역할 |
|---|---|
| `index.html` | 화면 구조와 기사 상세 dialog |
| `styles.css` | 반응형 카드·상세 화면 스타일 (외부 폰트·라이브러리 없음) |
| `app.js` | ID 저장, API 요청, 페이지 조회, 좋아요·해제, 안전한 텍스트 표시 |

1. localStorage의 `sai-news.backend-reader-id`를 읽습니다.
2. 새 키가 없고 기존 `sai-news.backend-user-id` 값이 있으면 동일한 값을 새 키로 옮겨 사용합니다. 기존 키는 지우지 않습니다.
3. 둘 다 없으면 `POST /api/user/anonymous`로 reader_id를 발급받아 저장합니다.
4. `POST /api/news/feed`에 `{reader_id, offset: 0}`을 보냅니다.
5. 다음 페이지는 응답의 next_offset을 그대로 보냅니다. null이면 더 보기 버튼을 숨깁니다.
6. 기사 제목이나 이미지를 누르면 이미 받은 본문을 dialog에 표시합니다. 별도 상세 API·조회 로깅은 없습니다.
7. 좋아요는 `PUT /api/news/{article_id}/like`, 해제는 DELETE로 `{reader_id}`를 보냅니다. 성공 후에만 화면 상태를 갱신합니다.

## Compose에 연결한 내용

```yaml
  nginx:
    image: nginx:stable-alpine
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:80"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - ./generate/output_with_thumbnail:/srv/images:ro
      - ./web:/usr/share/nginx/html:ro
    depends_on:
      api:
        condition: service_healthy
```

Nginx는 `/`에서 web 폴더를, `/api/`에서 api:8000을, `/images/`에서 /srv/images를 사용합니다.
프론트와 API가 같은 출처이므로 별도 CORS 설정이 필요하지 않습니다.

기존 DB의 localhost:8001 이미지 URL은 이 참고 프론트의 imageURL()에서 `/images/원래경로`로 연결합니다.
DB의 URL 값 자체는 변경하지 않습니다. 외부 HTTP(S) 이미지 URL은 그대로 사용합니다.

## 확인

- 새로고침 전후 독자 ID가 유지되는지 (하단 '내 독자 ID')
- 더 보기를 누르면 다음 기사가 추가되는지
- 좋아요 설정 후 새로고침해도 유지되는지
- 카드와 상세 화면의 좋아요 표시가 함께 갱신되는지
- 이미지 누락 시 대체 영역이 표시되는지

저장소 접근이 차단된 브라우저에서는 오류 안내를 표시하며 임의의 임시 ID로 대체하지 않습니다.
네트워크 재시도는 기존 ID와 offset을 유지합니다. 다른 탭에서 변경한 좋아요는 새로고침 시 반영됩니다.
