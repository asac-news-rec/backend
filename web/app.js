// Same-origin requests: browser → Nginx /api/* → FastAPI.
const READER_KEY = 'sai-news.backend-reader-id';
const LEGACY_KEY = 'sai-news.backend-user-id';
const feed = document.querySelector('#feed');
const status = document.querySelector('#status');
const nextButton = document.querySelector('#next');
const refreshButton = document.querySelector('#refresh');
const dialog = document.querySelector('#article-dialog');
const articles = new Map();
let readerId = null;
let nextOffset = 0;
let loading = false;
const pendingLikes = new Set();

function message(text = '', error = false) {
  status.textContent = text;
  status.classList.toggle('error', error);
}

async function request(path, method = 'POST', body) {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? {} : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : '요청을 처리하지 못했습니다.';
    throw new Error(`${response.status}: ${detail}`);
  }
  if (data === null) throw new Error('서버에서 JSON 응답을 받지 못했습니다.');
  return data;
}

async function ensureReader() {
  // Migrate the existing localStorage key without issuing a different identity.
  const saved = localStorage.getItem(READER_KEY) || localStorage.getItem(LEGACY_KEY);
  if (saved) {
    localStorage.setItem(READER_KEY, saved);
    return saved;
  }
  const result = await request('/user/anonymous');
  if (typeof result.reader_id !== 'string' || !result.reader_id) {
    throw new Error('독자 ID 응답을 확인하세요. reader_id가 필요합니다.');
  }
  localStorage.setItem(READER_KEY, result.reader_id);
  return result.reader_id;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function safeURL(value) {
  if (!value) return null;
  try {
    const url = new URL(value, location.origin);
    return ['http:', 'https:'].includes(url.protocol) ? url : null;
  } catch { return null; }
}

function imageURL(value) {
  const url = safeURL(value);
  if (!url) return null;
  // Existing DB images may still point to the old local :8001 image server.
  // Map only that known local form to Nginx; leave remote URLs untouched.
  if (['localhost', '127.0.0.1'].includes(url.hostname) && url.port === '8001') {
    return `/images${url.pathname}${url.search}`;
  }
  return url.href;
}

function dateLabel(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('ko-KR', {month: 'short', day: 'numeric'});
}

function refreshLikeButtons() {
  document.querySelectorAll('button[data-like-id]').forEach(button => {
    const item = articles.get(button.dataset.likeId);
    if (!item) return;
    button.textContent = item.is_liked ? '♥ 좋아요 해제' : '♡ 좋아요';
    button.setAttribute('aria-pressed', String(item.is_liked));
    button.disabled = pendingLikes.has(item.article_id);
  });
}

function likeButton(item) {
  const button = element('button', 'like-button');
  button.type = 'button';
  button.dataset.likeId = item.article_id;
  button.addEventListener('click', async () => {
    if (pendingLikes.has(item.article_id)) return;
    pendingLikes.add(item.article_id);
    refreshLikeButtons();
    try {
      const result = await request(`/news/${encodeURIComponent(item.article_id)}/like`,
        item.is_liked ? 'DELETE' : 'PUT', {reader_id: readerId});
      item.is_liked = result.is_liked;
      message('좋아요 상태를 저장했습니다.');
    } catch (error) {
      // Update only after success: preserve the previous UI state on failure.
      message(`좋아요 저장 실패: ${error.message}`, true);
    } finally {
      pendingLikes.delete(item.article_id);
      refreshLikeButtons();
    }
  });
  return button;
}

function placeholder() { return element('div', 'image-placeholder', 'SAI NEWS'); }

function renderCard(item) {
  const card = element('article', 'card');
  const thumbnail = element('button', 'thumbnail');
  thumbnail.type = 'button';
  thumbnail.setAttribute('aria-label', `${item.title} 기사 읽기`);
  const url = imageURL(item.image_url);
  if (url) {
    const image = element('img');
    image.src = url;
    image.alt = item.image_caption || item.title;
    image.loading = 'lazy';
    image.addEventListener('error', () => thumbnail.replaceChildren(placeholder()), {once: true});
    thumbnail.append(image);
  } else thumbnail.append(placeholder());
  thumbnail.addEventListener('click', () => showArticle(item));
  const meta = element('div', 'card-meta');
  meta.append(element('span', 'category', item.category), element('span', '', dateLabel(item.published_at)));
  if (item.is_synthetic) meta.append(element('span', 'synthetic', 'AI 생성'));
  const title = element('button', 'title-button');
  title.type = 'button';
  title.append(element('h3', '', item.title));
  title.addEventListener('click', () => showArticle(item));
  const bottom = element('div', 'card-bottom');
  bottom.append(element('span', 'publisher', item.publisher || item.author || ''), likeButton(item));
  card.append(thumbnail, meta, title, element('p', 'summary', item.summary), bottom);
  return card;
}

function showArticle(item) {
  const detail = document.querySelector('#detail');
  detail.replaceChildren();
  detail.append(element('p', 'detail-meta', `${item.category} · ${item.publisher || ''} · ${dateLabel(item.published_at)}`));
  const title = element('h2', '', item.title);
  title.id = 'detail-title';
  detail.append(title);
  if (item.subtitle) detail.append(element('p', 'subtitle', item.subtitle));
  const url = imageURL(item.image_url);
  if (url) {
    const image = element('img', 'detail-image');
    image.src = url;
    image.alt = item.image_caption || '';
    image.addEventListener('error', () => image.remove(), {once:true});
    detail.append(image);
  }
  if (item.image_caption) detail.append(element('p', 'caption', item.image_caption));
  if (item.is_synthetic) detail.append(element('p', 'caption', '이 기사는 AI로 생성한 합성 기사입니다.'));
  for (const text of Array.isArray(item.paragraphs) ? item.paragraphs : []) {
    detail.append(element('p', 'paragraph', text));
  }
  if (Array.isArray(item.tags)) detail.append(element('p', 'tags', item.tags.map(tag => `#${tag}`).join('  ')));
  const actions = element('div', 'detail-actions');
  actions.append(likeButton(item));
  const source = safeURL(item.url);
  if (source) {
    const link = element('a', '', '기사 링크 ↗');
    link.href = source.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
    actions.append(link);
  }
  detail.append(actions);
  refreshLikeButtons();
  dialog.showModal();
  dialog.scrollTop = 0;
  // No view/event API exists yet. Opening a detail does not record analytics.
}

async function loadPage(reset = false) {
  if (loading || (!reset && nextOffset === null)) return;
  loading = true;
  nextButton.disabled = true;
  refreshButton.disabled = true;
  feed.setAttribute('aria-busy', 'true');
  message(reset ? '최신 뉴스를 불러오고 있습니다.' : '뉴스를 불러오고 있습니다.');
  try {
    if (!readerId) readerId = await ensureReader();
    document.querySelector('#reader-id').textContent = readerId;
    const result = await request('/news/feed', 'POST', {reader_id: readerId, offset: reset ? 0 : nextOffset});
    if (!Array.isArray(result.items) || !(result.next_offset === null || Number.isInteger(result.next_offset))) {
      throw new Error('뉴스 응답의 items 또는 next_offset 형식을 확인하세요.');
    }
    // Clear only after a successful refresh; retain the previous feed on failure.
    if (reset) { articles.clear(); feed.replaceChildren(); }
    for (const item of result.items) {
      if (articles.has(item.article_id)) continue;
      articles.set(item.article_id, item);
      feed.append(renderCard(item));
    }
    nextOffset = result.next_offset;
    document.querySelector('#count').textContent = `${articles.size}개 기사`;
    document.querySelector('#page-note').textContent = nextOffset === null && articles.size ? '모든 기사를 확인했습니다.' : '';
    message(articles.size ? '' : '아직 등록된 기사가 없습니다.');
    refreshLikeButtons();
  } catch (error) {
    message(`불러오지 못했습니다. ${error.message}`, true);
  } finally {
    loading = false;
    feed.setAttribute('aria-busy', 'false');
    nextButton.disabled = false;
    nextButton.hidden = nextOffset === null;
    nextButton.textContent = '뉴스 더 보기 ↓';
    refreshButton.disabled = false;
  }
}

nextButton.addEventListener('click', () => loadPage());
refreshButton.addEventListener('click', () => loadPage(true));
document.querySelector('#close-dialog').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) {
  const box = dialog.getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
}});
loadPage();
