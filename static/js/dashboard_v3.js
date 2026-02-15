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
                ? sched.map(item => (
                    `<div class="list-item">#${item.id.slice(0, 6)} • ${formatTime(item.scheduled_time)}</div>`
                )).join('')
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
    list.innerHTML = items.map(item => `
        <div class="list-item">
            <div style="font-weight:600;">${item.hook || item.content_id || item.id}</div>
            <div class="muted">${formatTime(item.generated_at || item.scheduled_time || item.published_at)}</div>
        </div>
    `).join('');
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

window.runNow = runNow;
window.pauseSystem = pauseSystem;
