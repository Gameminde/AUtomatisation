document.addEventListener('DOMContentLoaded', () => {
    // Show skeleton loaders immediately
    showSkeletons();
    loadDashboard();
    setInterval(loadDashboard, 30000);
});

// ── Toast Notification System ───────────────────────
function ensureToastContainer() {
    if (!document.getElementById('toast-container')) {
        const c = document.createElement('div');
        c.id = 'toast-container';
        document.body.appendChild(c);
    }
}

function showToast(message, type = 'info', duration = 3500) {
    ensureToastContainer();
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i> ${message}`;
    document.getElementById('toast-container').appendChild(toast);
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
window.showToast = showToast;

// ── Skeleton Loaders ────────────────────────────────
function showSkeletons() {
    // KPI cards
    ['kpi-posts', 'kpi-reach', 'kpi-likes', 'kpi-engagement'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.classList.add('skeleton', 'skeleton-lg'); el.textContent = '\u00A0'; }
    });
    // Queue lists
    ['list-waiting', 'list-scheduled', 'list-published'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = [1, 2, 3].map(() =>
                '<div class="list-item skeleton" style="height:3rem;margin-bottom:0.4rem;">\u00A0</div>'
            ).join('');
        }
    });
}

function clearSkeletons() {
    document.querySelectorAll('.skeleton').forEach(el => el.classList.remove('skeleton', 'skeleton-lg'));
}

// ── Empty State Renderer ────────────────────────────
function renderEmptyState(icon, title, hint) {
    return `<div class="empty-state">
        <i class="fa-solid ${icon}"></i>
        <div class="empty-title">${title}</div>
        <div class="empty-hint">${hint}</div>
    </div>`;
}

// ── Dashboard Loading ───────────────────────────────
async function loadDashboard() {
    await Promise.all([
        loadSystemSnapshot(),
        loadAnalytics(),
        loadQueues()
    ]);
    clearSkeletons();
}

async function loadSystemSnapshot() {
    try {
        const data = await apiCall('/api/system/snapshot');
        const snap = data.snapshot || {};
        const nextRun = document.getElementById('next-run');
        if (nextRun) {
            nextRun.textContent = snap.next_run_at
                ? `Next run: ${formatTime(snap.next_run_at)}`
                : 'Not scheduled — set up your schedule';
        }
    } catch (e) {
        const nextRun = document.getElementById('next-run');
        if (nextRun) nextRun.textContent = 'Status unavailable';
    }
}

async function loadAnalytics() {
    try {
        const data = await apiCall('/api/analytics/overview');
        setKPI('kpi-posts', data.total_posts);
        setKPI('kpi-reach', data.total_reach);
        setKPI('kpi-likes', data.total_likes);
        setKPI('kpi-engagement', `${data.engagement_rate || 0}%`);
        renderInsights(data);
    } catch (e) {
        ['kpi-posts', 'kpi-reach', 'kpi-likes'].forEach(id => setKPI(id, '--'));
        setKPI('kpi-engagement', '--%');
    }
}

function setKPI(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove('skeleton', 'skeleton-lg');
        el.textContent = value ?? 0;
    }
}

function renderInsights(data) {
    const box = document.getElementById('insights-box');
    if (!box) return;
    const avg = data.avg_per_post;
    if (!avg || (!avg.likes && !avg.shares && !avg.comments)) {
        box.innerHTML = renderEmptyState('fa-lightbulb', 'No insights yet', 'Publish a few posts and insights will appear here.');
        return;
    }
    const items = [
        `Avg likes/post: ${avg.likes ?? 0}`,
        `Avg shares/post: ${avg.shares ?? 0}`,
        `Avg comments/post: ${avg.comments ?? 0}`
    ];
    box.innerHTML = items.map(i => `<div class="list-item">${i}</div>`).join('');
}

async function loadQueues() {
    try {
        const [pending, scheduled, published] = await Promise.all([
            apiCall('/api/content/pending?limit=5'),
            apiCall('/api/content/scheduled?limit=5'),
            apiCall('/api/content/published?limit=5'),
        ]);
        renderQueue('waiting', pending.pending || [], 'fa-inbox', 'No posts waiting', 'Content will appear here when generated.');
        renderQueue('scheduled', scheduled.scheduled || [], 'fa-calendar-check', 'Nothing scheduled', 'Schedule posts from the Studio page.');
        renderQueue('published', published.published || [], 'fa-paper-plane', 'No published posts', 'Your published posts will show here.');

        const pipeline = document.getElementById('pipeline-box');
        if (pipeline) {
            const sched = scheduled.scheduled || [];
            pipeline.innerHTML = sched.length
                ? sched.map(item => {
                    const badges = renderPlatformBadges(item);
                    return `<div class="list-item" style="display:flex; justify-content:space-between; align-items:center;">
                        <span>#${item.id.slice(0, 6)} • ${formatTime(item.scheduled_time)}</span>
                        ${badges}
                    </div>`;
                }).join('')
                : renderEmptyState('fa-route', 'Pipeline empty', 'Schedule content to see it in the pipeline.');
        }
    } catch (e) {
        ['waiting', 'scheduled', 'published'].forEach(type => {
            const list = document.getElementById(`list-${type}`);
            if (list) list.innerHTML = renderEmptyState('fa-circle-exclamation', 'Could not load', 'Check your connection.');
        });
    }
}

function renderQueue(type, items, emptyIcon, emptyTitle, emptyHint) {
    const list = document.getElementById(`list-${type}`);
    const count = document.getElementById(`count-${type}`);
    if (!list) return;
    if (count) count.textContent = items.length;
    if (!items.length) {
        list.innerHTML = renderEmptyState(emptyIcon, emptyTitle, emptyHint);
        return;
    }
    list.innerHTML = items.map(item => {
        const platformBadges = renderPlatformBadges(item);
        const postLinks = renderPostLinks(item);
        return `
        <div class="list-item">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.4rem;">
                <div style="font-weight:600; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${item.hook || item.content_id || item.id}</div>
                ${platformBadges}
            </div>
            <div class="muted" style="margin-top:0.2rem;">${formatTime(item.generated_at || item.scheduled_time || item.published_at)}</div>
            ${postLinks ? `<div style="margin-top:0.25rem; font-size:0.74rem;">${postLinks}</div>` : ''}
        </div>`;
    }).join('');
}

function renderPlatformBadges(item) {
    if (!item.platforms && !item.facebook_post_id && !item.instagram_post_id) return '';
    const platforms = (item.platforms || 'facebook').split(',').map(p => p.trim());
    const icons = platforms.map(p => {
        if (p === 'instagram') {
            const status = item.instagram_status;
            const color = status === 'published' ? '#E1306C' : (status ? '#ff6b6b' : '#E1306C');
            const title = status ? `Instagram: ${status}` : 'Instagram';
            return `<i class="fa-brands fa-instagram" style="color:${color};" title="${title}"></i>`;
        }
        if (p === 'facebook') {
            const status = item.facebook_status;
            const color = status === 'published' ? '#1877F2' : (status ? '#ff6b6b' : '#1877F2');
            const title = status ? `Facebook: ${status}` : 'Facebook';
            return `<i class="fa-brands fa-facebook-f" style="color:${color};" title="${title}"></i>`;
        }
        return '';
    }).filter(Boolean).join(' ');
    return icons ? `<span style="display:flex; gap:0.3rem; align-items:center; flex-shrink:0;">${icons}</span>` : '';
}

function renderPostLinks(item) {
    const parts = [];
    if (item.facebook_post_id) {
        parts.push(`<span class="muted"><i class="fa-brands fa-facebook-f" style="color:#1877F2;"></i> ID: <code style="font-size:0.74rem;">${item.facebook_post_id}</code></span>`);
    }
    if (item.instagram_post_id) {
        parts.push(`<span class="muted"><i class="fa-brands fa-instagram" style="color:#E1306C;"></i> ID: <code style="font-size:0.74rem;">${item.instagram_post_id}</code></span>`);
    }
    return parts.join(' &nbsp; ');
}

// ── Actions ─────────────────────────────────────────
async function runNow() {
    try {
        showToast('Starting pipeline...', 'info');
        await apiCall('/api/actions/run-now', 'POST');
        showToast('Pipeline triggered successfully!', 'success');
    } catch (e) {
        showToast(`Failed: ${e.message}`, 'error');
    }
}

async function pauseSystem() {
    try {
        await apiCall('/api/actions/pause', 'POST');
        showToast('System paused', 'warning');
    } catch (e) {
        showToast(`Failed: ${e.message}`, 'error');
    }
}

function formatTime(value) {
    if (!value) return '--';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '--';
    return d.toLocaleString();
}

async function runScheduleNow() {
    try {
        const platforms = [];
        if (document.getElementById('sched-to-facebook')?.checked) platforms.push('facebook');
        if (document.getElementById('sched-to-instagram')?.checked) platforms.push('instagram');
        if (!platforms.length) {
            showToast('Select at least one platform to schedule for.', 'error');
            return;
        }
        showToast('Scheduling posts...', 'info');
        const result = await apiCall('/api/actions/schedule', 'POST', { days: 7, platforms });
        showToast(`Scheduled ${result.scheduled_count || 0} posts for ${result.platforms || 'facebook'}`, 'success');
        await loadDashboard();
    } catch (e) {
        showToast(`Schedule failed: ${e.message}`, 'error');
    }
}

window.runNow = runNow;
window.pauseSystem = pauseSystem;
window.runScheduleNow = runScheduleNow;
