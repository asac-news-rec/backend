import { setBehaviorCollection } from './behavior-events.js';
import { getBackendReaderId } from './reader-identity.js';
export { getBackendReaderId } from './reader-identity.js';
import { backendImageUrl } from './image-url.js';
function readList(value, key) {
    if (!value || typeof value !== 'object' || !(key in value))
        throw new Error('INVALID_BACKEND_CATEGORIES');
    const list = value[key];
    if (!Array.isArray(list) || list.some(item => typeof item !== 'string'))
        throw new Error('INVALID_BACKEND_CATEGORIES');
    return list;
}
export async function getBackendCategories({ fetchImpl = fetch } = {}) {
    return readList(await request('/category', undefined, 'POST', fetchImpl), 'category_list');
}
export async function getBackendSubcategories(category, { fetchImpl = fetch } = {}) {
    if (!category)
        throw new Error('INVALID_CATEGORY');
    return readList(await request('/subcategory', { category }, 'POST', fetchImpl), 'sub_category_list');
}
async function request(route, body, method = 'POST', fetchImpl = fetch) {
    const response = await fetchImpl('/api' + route, { method, credentials: 'same-origin', cache: 'no-store',
        ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
    if (!response.ok)
        throw new Error(`BACKEND_HTTP_${response.status}`);
    return response.json();
}
function isFeedCursor(value) {
    return value === null || Boolean(value && typeof value.published_at === 'string' && Number.isFinite(Date.parse(value.published_at)) &&
        typeof value.article_id === 'string' && value.article_id.length && Number.isSafeInteger(value.returned_count) && value.returned_count > 0);
}
export async function getBackendPage(cursor = null, { fetchImpl = fetch, getReaderId = getBackendReaderId, filters = {} } = {}) {
    const readerId = await getReaderId();
    const response = await request('/news/feed', { ...(cursor === null ? {} : { cursor }), ...(filters.category ? { category: filters.category } : {}), ...(filters.subcategory ? { subcategory: filters.subcategory } : {}) }, 'POST', fetchImpl);
    if (!response || (response.reader_id !== undefined && response.reader_id !== readerId) || typeof response.request_id !== 'string' || !Number.isFinite(Date.parse(response.served_at)) ||
        !Array.isArray(response.items) || !isFeedCursor(response.next_cursor))
        throw new Error('INVALID_BACKEND_FEED');
    const items = response.items.map((item) => {
        if (!item || typeof item.article_id !== 'string' || typeof item.impression_id !== 'string' ||
            !Number.isSafeInteger(item.position) || item.position < 1 || typeof item.title !== 'string' ||
            !Array.isArray(item.paragraphs) || item.paragraphs.some((value) => typeof value !== 'string') ||
            typeof item.category !== 'string' || !Number.isFinite(Date.parse(item.published_at)) ||
            typeof item.is_synthetic !== 'boolean' || typeof item.is_liked !== 'boolean')
            throw new Error('INVALID_BACKEND_ARTICLE');
        const article = { id: item.article_id, title: item.title, summary: item.summary ?? '', paragraphs: item.paragraphs,
            body: item.paragraphs.join('\n\n'), category: item.category, publisher: item.publisher ?? '언론사 미제공',
            subcategory: item.subcategory ?? null, publishedAt: item.published_at, imageUrl: backendImageUrl(item.image_url), imageCaption: item.image_caption ?? null,
            synthetic: item.is_synthetic, impressionId: item.impression_id, requestId: response.request_id, art: 'library' };
        return { article, rank: item.position, reason: '', impressionId: item.impression_id, isLiked: item.is_liked };
    });
    if (typeof response.collection_enabled === 'boolean')
        setBehaviorCollection(response.collection_enabled);
    return { generatedAt: response.served_at, strategy: 'backend_latest', requestId: response.request_id,
        items, nextCursor: response.next_cursor };
}
export async function changeBackendLike(articleId, liked, { fetchImpl = fetch } = {}) {
    const result = await request(`/news/${encodeURIComponent(articleId)}/like`, undefined, liked ? 'PUT' : 'DELETE', fetchImpl);
    if (!result || result.article_id !== articleId || result.is_liked !== liked || typeof result.changed !== 'boolean')
        throw new Error('INVALID_BACKEND_LIKE');
    return result;
}
