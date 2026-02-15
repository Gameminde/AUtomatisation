document.addEventListener('DOMContentLoaded', () => {
    refreshShellStatus();
    setInterval(refreshShellStatus, 60000);
    loadPages();
});

async function refreshShellStatus() {
    try {
        const data = await apiCall('/api/system/snapshot');
        const snap = data.snapshot || {};
        const dbChip = document.getElementById('db-mode-chip');
        const apChip = document.getElementById('approval-chip');
        if (dbChip) dbChip.textContent = `DB: ${snap.db_mode || 'sqlite'}`;
        if (apChip) apChip.textContent = `Approval: ${snap.approval_mode ? 'ON' : 'OFF'}`;
    } catch (e) {
        // Silent
    }
}

async function loadPages() {
    const select = document.getElementById('pageSelect');
    if (!select) return;
    try {
        const data = await apiCall('/api/pages');
        const pages = data.pages || [];
        select.innerHTML = '<option value=\"\">Select Page...</option>' + pages.map(p => (
            `<option value=\"${p.page_id}\">${p.page_name}</option>`
        )).join('');
    } catch (e) {
        // silent
    }
}
