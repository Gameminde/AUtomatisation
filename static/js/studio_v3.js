/**
 * Studio v3 — Canvas WYSIWYG Editor
 * Real-time preview: draws background, photo zone, title text, and logo bar.
 */

// ── Toast ──
function showToast(msg, type = 'info', dur = 3000) {
    let c = document.getElementById('toast-container');
    if (!c) { c = document.createElement('div'); c.id = 'toast-container'; c.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:0.4rem;pointer-events:none;'; document.body.appendChild(c); }
    const t = document.createElement('div'); t.className = `toast ${type}`; t.textContent = msg; t.style.pointerEvents = 'auto';
    c.appendChild(t); setTimeout(() => { t.classList.add('fade-out'); setTimeout(() => t.remove(), 300); }, dur);
}

// ── State ──
let currentContent = null;
let templates = [];
let selectedTemplateId = null;
let bgImage = null;        // Background Image object
let photoImage = null;     // Content photo Image object
let logoImage = null;      // @SmartEraPro logo strip

const CANVAS_W = 1080;
const CANVAS_H = 1350;

// Default template config (matches the example image style)
const DEFAULT_TPL = {
    id: 'smartera_classic',
    name: 'SmartEra Classic',
    bg_color: '#0c0f14',
    // Logo bar
    logo_bar_y: 20,
    logo_bar_h: 60,
    // Photo area
    photo_y: 120,
    photo_h: 700,
    photo_x: 35,
    photo_w: 1010,
    photo_radius: 8,
    // Title area
    title_y: 880,
    title_h: 350,
    title_color: '#ffc832',
    title_size: 72,
    title_align: 'center',
    // Branding
    brand_text: '@SmartEraPro',
    brand_color: '#ffffff',
};

// Template presets
const TEMPLATE_PRESETS = [
    {
        ...DEFAULT_TPL,
    },
    {
        id: 'dark_bold',
        name: 'Dark Bold',
        bg_color: '#111111',
        photo_y: 100, photo_h: 750, photo_x: 0, photo_w: 1080, photo_radius: 0,
        title_y: 900, title_h: 350, title_color: '#ffffff', title_size: 80,
        title_align: 'center', brand_text: '@SmartEraPro', brand_color: '#aaaaaa',
        logo_bar_y: 20, logo_bar_h: 60,
    },
    {
        id: 'gold_elegant',
        name: 'Gold Elegant',
        bg_color: '#0a0a0a',
        photo_y: 140, photo_h: 650, photo_x: 60, photo_w: 960, photo_radius: 16,
        title_y: 850, title_h: 400, title_color: '#ffd700', title_size: 68,
        title_align: 'center', brand_text: '@SmartEraPro', brand_color: '#ffd700',
        logo_bar_y: 25, logo_bar_h: 60,
    },
    {
        id: 'clean_light',
        name: 'Clean Light',
        bg_color: '#f5f5f5',
        photo_y: 120, photo_h: 700, photo_x: 40, photo_w: 1000, photo_radius: 12,
        title_y: 880, title_h: 370, title_color: '#1a1a1a', title_size: 66,
        title_align: 'center', brand_text: '@SmartEraPro', brand_color: '#333333',
        logo_bar_y: 20, logo_bar_h: 60,
    },
    {
        id: 'red_breaking',
        name: 'Breaking News',
        bg_color: '#1a0000',
        photo_y: 130, photo_h: 680, photo_x: 30, photo_w: 1020, photo_radius: 4,
        title_y: 860, title_h: 380, title_color: '#ff3333', title_size: 76,
        title_align: 'center', brand_text: '@SmartEraPro', brand_color: '#ff6666',
        logo_bar_y: 20, logo_bar_h: 60,
    },
    {
        id: 'ocean_calm',
        name: 'Ocean Calm',
        bg_color: '#0a1628',
        photo_y: 130, photo_h: 700, photo_x: 50, photo_w: 980, photo_radius: 20,
        title_y: 890, title_h: 360, title_color: '#7cc4fa', title_size: 64,
        title_align: 'center', brand_text: '@SmartEraPro', brand_color: '#7cc4fa',
        logo_bar_y: 22, logo_bar_h: 60,
    },
];

// ── DOM Ready ──
document.addEventListener('DOMContentLoaded', () => {
    loadContentList();
    renderTemplateStrip();
    selectTemplatePreset(TEMPLATE_PRESETS[0].id);

    document.getElementById('search-input').addEventListener('input', debounce(loadContentList, 300));
    document.getElementById('status-filter').addEventListener('change', loadContentList);
    document.getElementById('text-color').addEventListener('input', (e) => {
        document.getElementById('color-label').textContent = e.target.value.toUpperCase();
        renderCanvas();
    });
});

// ── Canvas Rendering ──
function renderCanvas() {
    const canvas = document.getElementById('live-canvas');
    const ctx = canvas.getContext('2d');
    const tpl = TEMPLATE_PRESETS.find(t => t.id === selectedTemplateId) || DEFAULT_TPL;

    // 1. Background
    if (bgImage) {
        ctx.drawImage(bgImage, 0, 0, CANVAS_W, CANVAS_H);
    } else {
        ctx.fillStyle = tpl.bg_color;
        ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
        // Add subtle noise/texture for dark themes
        if (isColorDark(tpl.bg_color)) {
            drawNoiseTexture(ctx);
        }
    }

    // 2. Photo zone
    ctx.save();
    roundRect(ctx, tpl.photo_x, tpl.photo_y, tpl.photo_w, tpl.photo_h, tpl.photo_radius);
    ctx.clip();
    if (photoImage) {
        drawCoverImage(ctx, photoImage, tpl.photo_x, tpl.photo_y, tpl.photo_w, tpl.photo_h);
    } else {
        // Placeholder
        ctx.fillStyle = 'rgba(255,255,255,0.05)';
        ctx.fillRect(tpl.photo_x, tpl.photo_y, tpl.photo_w, tpl.photo_h);
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.font = '48px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('📷 Photo Area', tpl.photo_x + tpl.photo_w / 2, tpl.photo_y + tpl.photo_h / 2);
    }
    ctx.restore();

    // 3. Logo bar (top)
    drawLogoBand(ctx, tpl);

    // 4. Title text (bottom)
    const titleText = document.getElementById('hook-input')?.value || '';
    const textColor = document.getElementById('text-color')?.value || tpl.title_color;
    if (titleText) {
        drawTitleText(ctx, titleText, textColor, tpl);
    } else {
        // Draw placeholder text
        ctx.fillStyle = 'rgba(255,255,255,0.1)';
        ctx.font = `bold ${tpl.title_size}px "IBM Plex Sans Arabic", "Space Grotesk", sans-serif`;
        ctx.textAlign = tpl.title_align;
        const tx = tpl.title_align === 'center' ? CANVAS_W / 2 : 60;
        ctx.fillText('Type your title here...', tx, tpl.title_y + tpl.title_h / 2);
    }
}

function drawTitleText(ctx, text, color, tpl) {
    ctx.fillStyle = color;
    const fontSize = tpl.title_size;
    ctx.font = `bold ${fontSize}px "IBM Plex Sans Arabic", "Space Grotesk", sans-serif`;
    ctx.textAlign = tpl.title_align;
    ctx.textBaseline = 'top';

    const maxWidth = CANVAS_W - 120;
    const lineHeight = fontSize * 1.4;
    const lines = wrapText(ctx, text, maxWidth);
    const maxLines = Math.floor(tpl.title_h / lineHeight);
    const visibleLines = lines.slice(0, maxLines);

    // Vertically center the text in the title area
    const totalTextH = visibleLines.length * lineHeight;
    let startY = tpl.title_y + (tpl.title_h - totalTextH) / 2;

    const tx = tpl.title_align === 'center' ? CANVAS_W / 2 : 60;

    // Text shadow for readability
    ctx.shadowColor = 'rgba(0,0,0,0.5)';
    ctx.shadowBlur = 8;
    ctx.shadowOffsetX = 2;
    ctx.shadowOffsetY = 2;

    visibleLines.forEach((line, i) => {
        ctx.fillText(line, tx, startY + i * lineHeight);
    });

    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
}

function drawLogoBand(ctx, tpl) {
    const y = tpl.logo_bar_y;
    const brandColor = tpl.brand_color || '#ffffff';

    // Social icons as simple text (YouTube, Facebook, X)
    ctx.fillStyle = brandColor;
    ctx.font = 'bold 36px "Space Grotesk", sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';

    const iconY = y + 30;
    // Simple circle icons
    const icons = ['▶', 'f', '𝕏'];
    let ix = 40;
    icons.forEach(icon => {
        // Circle bg
        ctx.beginPath();
        ctx.arc(ix + 16, iconY, 22, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.fill();

        // Icon
        ctx.fillStyle = brandColor;
        ctx.font = 'bold 24px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(icon, ix + 16, iconY + 1);
        ix += 56;
    });

    // Brand name
    ctx.fillStyle = brandColor;
    ctx.font = 'bold 32px "Space Grotesk", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(tpl.brand_text, ix + 10, iconY);
}

function drawNoiseTexture(ctx) {
    // Subtle geometric lines like the example
    ctx.strokeStyle = 'rgba(255,255,255,0.03)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 8; i++) {
        ctx.beginPath();
        ctx.moveTo(Math.random() * CANVAS_W, Math.random() * CANVAS_H);
        ctx.lineTo(Math.random() * CANVAS_W, Math.random() * CANVAS_H);
        ctx.stroke();
    }
    // Subtle golden noise dots
    for (let i = 0; i < 200; i++) {
        const x = Math.random() * CANVAS_W;
        const y = Math.random() * CANVAS_H;
        const a = Math.random() * 0.08;
        ctx.fillStyle = `rgba(255, 200, 50, ${a})`;
        ctx.fillRect(x, y, 1, 1);
    }
}

// ── Helpers ──
function wrapText(ctx, text, maxWidth) {
    const words = text.split(' ');
    const lines = [];
    let current = '';
    words.forEach(word => {
        const test = current ? current + ' ' + word : word;
        if (ctx.measureText(test).width > maxWidth && current) {
            lines.push(current);
            current = word;
        } else {
            current = test;
        }
    });
    if (current) lines.push(current);
    return lines;
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

function drawCoverImage(ctx, img, x, y, w, h) {
    const iw = img.naturalWidth || img.width;
    const ih = img.naturalHeight || img.height;
    const scale = Math.max(w / iw, h / ih);
    const sw = iw * scale, sh = ih * scale;
    const sx = x + (w - sw) / 2, sy = y + (h - sh) / 2;
    ctx.drawImage(img, sx, sy, sw, sh);
}

function isColorDark(hex) {
    const c = hex.replace('#', '');
    const r = parseInt(c.substr(0, 2), 16);
    const g = parseInt(c.substr(2, 2), 16);
    const b = parseInt(c.substr(4, 2), 16);
    return (r * 0.299 + g * 0.587 + b * 0.114) < 128;
}

// ── Template Strip ──
function renderTemplateStrip() {
    const grid = document.getElementById('template-grid');
    // Generate mini canvas previews for each template
    grid.innerHTML = TEMPLATE_PRESETS.map(t => {
        return `
            <div class="tpl-item ${selectedTemplateId === t.id ? 'active' : ''}"
                 data-id="${t.id}"
                 onclick="selectTemplatePreset('${t.id}')"
                 title="${t.name}">
                <canvas width="50" height="62" id="mini-${t.id}"></canvas>
            </div>`;
    }).join('');

    // Render mini previews
    requestAnimationFrame(() => {
        TEMPLATE_PRESETS.forEach(t => {
            const mini = document.getElementById(`mini-${t.id}`);
            if (!mini) return;
            const mc = mini.getContext('2d');
            mc.fillStyle = t.bg_color;
            mc.fillRect(0, 0, 50, 62);
            // Mini photo zone
            const sx = (t.photo_x / CANVAS_W) * 50;
            const sy = (t.photo_y / CANVAS_H) * 62;
            const sw = (t.photo_w / CANVAS_W) * 50;
            const sh = (t.photo_h / CANVAS_H) * 62;
            mc.fillStyle = 'rgba(255,255,255,0.1)';
            mc.fillRect(sx, sy, sw, sh);
            // Mini title zone
            const ty = (t.title_y / CANVAS_H) * 62;
            mc.fillStyle = t.title_color;
            mc.fillRect(8, ty, 34, 3);
            mc.fillRect(12, ty + 5, 26, 2);
        });
    });
}

function selectTemplatePreset(id) {
    selectedTemplateId = id;
    document.querySelectorAll('.tpl-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === id);
    });
    const tpl = TEMPLATE_PRESETS.find(t => t.id === id);
    if (tpl) {
        document.getElementById('text-color').value = tpl.title_color;
        document.getElementById('color-label').textContent = tpl.title_color.toUpperCase();
    }
    renderCanvas();
    showToast(`Template: ${tpl ? tpl.name : id}`, 'info');
}

// ── Image Upload ──
function handleBgUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => { bgImage = img; renderCanvas(); showToast('Background set ✅', 'success'); };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

function handlePhotoUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => { photoImage = img; renderCanvas(); showToast('Photo set ✅', 'success'); };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

// ── Export ──
function exportCanvas() {
    const canvas = document.getElementById('live-canvas');
    const link = document.createElement('a');
    link.download = `post_${Date.now()}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
    showToast('Exported PNG ✅', 'success');
}

// ── Content List ──
async function loadContentList() {
    const q = document.getElementById('search-input').value.trim();
    const status = document.getElementById('status-filter').value;
    const params = new URLSearchParams({ limit: '50' });
    if (q) params.set('q', q);
    if (status) params.set('status', status);
    try {
        const data = await apiCall(`/api/content/list?${params}`);
        renderContentList(data.content || []);
    } catch (e) {
        document.getElementById('content-list').innerHTML = '<div style="text-align:center;padding:2rem;opacity:0.4;"><i class="fa-solid fa-inbox" style="font-size:1.5rem;"></i><div style="font-size:0.8rem;margin-top:0.4rem;">Could not load</div></div>';
    }
}

function renderContentList(items) {
    const list = document.getElementById('content-list');
    if (!items.length) {
        list.innerHTML = '<div style="text-align:center;padding:2rem;opacity:0.4;"><i class="fa-solid fa-inbox" style="font-size:1.5rem;"></i><div style="font-size:0.8rem;margin-top:0.4rem;">No content</div></div>';
        return;
    }
    list.innerHTML = items.map(item => `
        <div class="list-item ${currentContent?.id === item.id ? 'active' : ''}"
             onclick="selectContent('${item.id}')" style="cursor:pointer;">
            <div style="font-weight:600;font-size:0.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                ${item.hook || item.generated_text?.substring(0, 35) || 'Untitled'}
            </div>
            <div class="muted" style="font-size:0.7rem;">
                <span class="badge" style="font-size:0.6rem;">${item.status || '?'}</span>
                ${formatTime(item.generated_at)}
            </div>
        </div>
    `).join('');
}

// ── Content Selection ──
async function selectContent(id) {
    try {
        const data = await apiCall(`/api/content/${id}`);
        currentContent = data;
        document.getElementById('content-id').textContent = `#${id.substring(0, 8)}`;
        document.getElementById('hook-input').value = data.hook || '';
        document.getElementById('text-input').value = data.generated_text || '';
        document.getElementById('hashtags-input').value = Array.isArray(data.hashtags) ? data.hashtags.join(' ') : (data.hashtags || '');

        // Highlight
        document.querySelectorAll('#content-list .list-item').forEach(el => el.classList.remove('active'));
        event?.currentTarget?.classList.add('active');

        // Try loading content image as photo
        try {
            const res = await apiFetch(`/api/content/${id}/image`);
            if (res.ok) {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const img = new Image();
                img.onload = () => { photoImage = img; renderCanvas(); };
                img.src = url;
            }
        } catch (_) { }

        renderCanvas();
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

// ── Actions ──
async function saveContent() {
    if (!currentContent) return showToast('Select content first', 'warning');
    try {
        await apiCall(`/api/content/${currentContent.id}`, 'PUT', {
            generated_text: document.getElementById('text-input').value,
            hashtags: document.getElementById('hashtags-input').value,
            hook: document.getElementById('hook-input').value,
        });
        showToast('Saved ✅', 'success');
    } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

async function approveContent() {
    if (!currentContent) return showToast('Select content first', 'warning');
    try {
        await apiCall(`/api/content/${currentContent.id}/approve`, 'POST');
        showToast('Approved ✅', 'success'); loadContentList();
    } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

async function rejectContent() {
    if (!currentContent) return showToast('Select content first', 'warning');
    try {
        await apiCall(`/api/content/${currentContent.id}/reject`, 'POST', { action: 'reject' });
        showToast('Rejected', 'warning'); loadContentList();
    } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

async function regenerateContent() {
    if (!currentContent) return showToast('Select content first', 'warning');
    try {
        showToast('Regenerating... ⏳', 'info');
        const data = await apiCall(`/api/content/${currentContent.id}/regenerate`, 'POST', { style: 'emotional' });
        if (data.new_text) { document.getElementById('text-input').value = data.new_text; }
        showToast(data.message || 'Done ✨', 'success');
    } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

async function publishContent() {
    if (!currentContent) return showToast('Select content first', 'warning');
    try {
        await apiCall('/api/actions/publish-content', 'POST', { content_id: currentContent.id });
        showToast('Publishing... 🚀', 'success');
    } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

// ── Helpers ──
function formatTime(v) {
    if (!v) return '--';
    const d = new Date(v);
    return isNaN(d) ? '--' : d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function debounce(fn, ms) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// Global scope
window.selectContent = selectContent;
window.selectTemplatePreset = selectTemplatePreset;
window.handleBgUpload = handleBgUpload;
window.handlePhotoUpload = handlePhotoUpload;
window.exportCanvas = exportCanvas;
window.saveContent = saveContent;
window.approveContent = approveContent;
window.rejectContent = rejectContent;
window.regenerateContent = regenerateContent;
window.publishContent = publishContent;
window.renderCanvas = renderCanvas;
