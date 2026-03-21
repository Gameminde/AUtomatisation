document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadInstagramStatus();
});

async function loadSettings() {
    try {
        const snapshot = await apiCall('/api/system/snapshot');
        document.getElementById('approval-toggle').checked = !!snapshot.snapshot?.approval_mode;
    } catch (_) {}
}

async function loadInstagramStatus() {
    const box = document.getElementById('instagram-status-box');
    const hint = document.getElementById('instagram-connect-hint');
    if (!box) return;
    try {
        const data = await apiCall('/api/instagram/status');
        if (data.connected) {
            const handle = data.username ? `@${data.username}` : data.instagram_account_id;
            box.innerHTML = `
                <div style="display:flex; align-items:center; gap:0.6rem; padding:0.6rem 0.8rem; border-radius:0.5rem; background:rgba(225,48,108,0.08);">
                    <i class="fa-brands fa-instagram" style="color:#E1306C; font-size:1.2rem;"></i>
                    <div>
                        <div style="font-weight:600;">${handle}</div>
                        <div class="muted" style="font-size:0.78rem;">Connected — posts will publish to Instagram when you select it</div>
                    </div>
                    <span class="badge success" style="margin-left:auto;">Connected</span>
                </div>`;
            if (hint) hint.style.display = 'none';
        } else {
            box.innerHTML = `
                <div style="display:flex; align-items:center; gap:0.6rem; padding:0.6rem 0.8rem; border-radius:0.5rem; background:rgba(255,255,255,0.04);">
                    <i class="fa-brands fa-instagram" style="color:var(--text-dim); font-size:1.2rem;"></i>
                    <div>
                        <div style="font-weight:600; color:var(--text-dim);">Not connected</div>
                        <div class="muted" style="font-size:0.78rem;">${data.reason || 'Link your Instagram Business account to your Facebook Page.'}</div>
                    </div>
                    <span class="badge warn" style="margin-left:auto;">Not linked</span>
                </div>`;
            if (hint) hint.style.display = 'block';
        }
    } catch (e) {
        if (box) box.innerHTML = '<div class="muted">Could not check Instagram status.</div>';
    }
}

async function saveLanguageRatio() {
    const payload = {
        AR: parseInt(document.getElementById('lang-ar').value || '0', 10),
        FR: parseInt(document.getElementById('lang-fr').value || '0', 10),
        EN: parseInt(document.getElementById('lang-en').value || '0', 10),
    };
    await apiCall('/api/brand/language-ratio', 'POST', payload);
    alert('Saved.');
}

async function saveApiKeys() {
    const payload = {
        facebook_token: document.getElementById('facebook-token').value.trim(),
        facebook_page_id: document.getElementById('facebook-page-id').value.trim(),
        gemini_key: document.getElementById('gemini-key').value.trim(),
        openrouter_key: document.getElementById('openrouter-key').value.trim(),
        pexels_key: document.getElementById('pexels-key').value.trim(),
    };
    await apiCall('/api/config/api-keys', 'POST', payload);
    alert('Keys saved.');
}

async function connectSupabase() {
    const payload = {
        mode: 'supabase',
        supabase_url: document.getElementById('supabase-url').value.trim(),
        supabase_key: document.getElementById('supabase-key').value.trim(),
    };
    await apiCall('/api/config/database', 'POST', payload);
    alert('Supabase configured. Restart dashboard.');
}

async function useSqlite() {
    await apiCall('/api/config/database', 'POST', { mode: 'sqlite' });
    alert('SQLite enabled.');
}

async function saveApprovalMode() {
    const enabled = document.getElementById('approval-toggle').checked;
    await apiCall('/api/config/approval-mode', 'POST', { enabled });
    alert('Approval mode updated. Restart dashboard.');
}

window.saveLanguageRatio = saveLanguageRatio;
window.saveApiKeys = saveApiKeys;
window.connectSupabase = connectSupabase;
window.useSqlite = useSqlite;
window.saveApprovalMode = saveApprovalMode;
