import { recordBehavior } from './behavior-events.js';
import { changeBackendLike } from './backend-api.js';
const liked = new Set();
let status = 'loading';
let pending = false;
const notice = document.createElement('p');
notice.className = 'like-notice';
notice.setAttribute('role', 'status');
document.body.append(notice);
export function likeButton(id) { const safe = String(id).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); return `<button class="like-button" data-like="${safe}" aria-label="기사 좋아요" aria-pressed="${liked.has(id)}" ${pending || status === 'loading' ? 'disabled' : ''}>♡ 좋아요</button>`; }
function update() { document.querySelectorAll('[data-like]').forEach(button => { const active = liked.has(button.dataset.like ?? ''); button.setAttribute('aria-pressed', String(active)); button.textContent = '♡ 좋아요'; button.disabled = pending || status === 'loading'; }); }
export function seedBackendLikes(items, reset = false) { if (reset)
    liked.clear(); for (const item of items) {
    if (item.isLiked)
        liked.add(item.article.id);
    else
        liked.delete(item.article.id);
} status = 'ready'; update(); }
document.addEventListener('click', async (event) => {
    const button = event.target instanceof Element ? event.target.closest('[data-like]') : null;
    if (!button || pending)
        return;
    const detail = button.closest('.article-page');
    const impression = detail ?? button.closest('.news-row')?.querySelector('.card');
    const context = { id: impression?.dataset.impressionId, page: detail ? 'detail' : 'list', at: new Date().toISOString() };
    pending = true;
    update();
    notice.textContent = '';
    try {
        const id = button.dataset.like;
        if (id === undefined)
            return;
        const desired = !liked.has(id);
        const result = await changeBackendLike(id, desired);
        if (result.changed && event.isTrusted)
            recordBehavior(desired ? 'like' : 'unlike', context.id, context.page, { event_time: context.at });
        if (desired)
            liked.add(id);
        else
            liked.delete(id);
        notice.textContent = '';
        window.dispatchEvent(new Event('likes-changed'));
    }
    catch {
        notice.textContent = '저장하지 못했어요. 다시 시도해 주세요.';
    }
    finally {
        pending = false;
        update();
    }
});
