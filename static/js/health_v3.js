document.addEventListener('DOMContentLoaded', () => {
    loadHealth();
});

async function loadHealth() {
    try {
        const data = await apiCall('/api/health/status');
        const err = data.last_error;
        document.getElementById('error-message').textContent = err ? err.message : 'No recent errors';
        document.getElementById('error-time').textContent = err ? err.time : '-';

        const cooldown = data.cooldown || {};
        document.getElementById('cooldown-status').textContent = cooldown.active ? 'Active' : 'Ready';
        document.getElementById('cooldown-reason').textContent = cooldown.reason || '-';

        const tokens = data.tokens || {};
        document.getElementById('token-facebook').textContent = `FB: ${tokens.facebook ? 'OK' : 'Missing'}`;
        document.getElementById('token-ai').textContent = `AI: ${tokens.ai ? 'OK' : 'Missing'}`;
        document.getElementById('token-pexels').textContent = `Pexels: ${tokens.pexels ? 'OK' : 'Missing'}`;
    } catch (_) {}

    try {
        const events = await apiCall('/api/health/events');
        const list = document.getElementById('events-list');
        list.innerHTML = (events.events || []).map(e => `<div class="list-item">${e.type}: ${e.message} (${e.time})</div>`).join('');
    } catch (_) {}
}

async function testService(name) {
    try {
        const res = await apiCall(`/api/health/test/${name}`);
        alert(`${name}: ${res.success ? 'OK' : 'Fail'}`);
    } catch (e) {
        alert(`${name}: Error`);
    }
}

window.testService = testService;
