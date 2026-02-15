document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
});

async function loadSettings() {
    try {
        const snapshot = await apiCall('/api/system/snapshot');
        document.getElementById('approval-toggle').checked = !!snapshot.snapshot?.approval_mode;
    } catch (_) {}
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
