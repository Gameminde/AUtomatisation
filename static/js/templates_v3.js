let currentTab = 'image';
let currentTemplate = null;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('tab-image').addEventListener('click', () => switchTab('image'));
    document.getElementById('tab-text').addEventListener('click', () => switchTab('text'));
    switchTab('image');
});

async function switchTab(tab) {
    currentTab = tab;
    document.getElementById('tab-image').classList.toggle('btn-primary', tab === 'image');
    document.getElementById('tab-text').classList.toggle('btn-primary', tab === 'text');
    await loadTemplates();
}

async function loadTemplates() {
    const data = await apiCall('/api/brand/templates');
    const grid = document.getElementById('templates-grid');
    const items = currentTab === 'image' ? (data.image_templates || []) : (data.text_templates || []);

    if (!items.length) {
        grid.innerHTML = '<div class="muted">No templates found.</div>';
        return;
    }

    grid.innerHTML = items.map((t, idx) => `
        <div class="card" onclick="openModal(${idx})" style="cursor:pointer;">
            <div style="font-weight:700;">${t.name || t.title || 'Template'}</div>
            <div class="muted">${t.description || t.language || ''}</div>
        </div>
    `).join('');

    grid.dataset.items = JSON.stringify(items);
}

function openModal(index) {
    const items = JSON.parse(document.getElementById('templates-grid').dataset.items || '[]');
    currentTemplate = items[index];
    document.getElementById('modal-title').textContent = currentTemplate.name || currentTemplate.title || 'Template';
    document.getElementById('modal-body').innerHTML = `<pre>${JSON.stringify(currentTemplate, null, 2)}</pre>`;
    document.getElementById('template-modal').classList.add('active');
}

function closeModal() {
    document.getElementById('template-modal').classList.remove('active');
}

async function selectTemplate() {
    if (!currentTemplate) return;
    const id = currentTemplate.id || currentTemplate.name || currentTemplate.title;
    await apiCall('/api/brand/template-select', 'POST', { type: currentTab, id });
    alert('Template selected.');
    closeModal();
}

window.openModal = openModal;
window.closeModal = closeModal;
window.selectTemplate = selectTemplate;
