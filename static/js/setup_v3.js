async function saveSetup() {
    const provider = document.querySelector('input[name="provider"]:checked').value;
    const payload = {
        fb_token: document.getElementById('fb-token').value.trim(),
        ai_provider: provider,
        ai_key: document.getElementById('ai-key').value.trim(),
        pexels_key: document.getElementById('pexels-key').value.trim(),
    };
    try {
        const res = await apiCall('/api/setup/save', 'POST', payload);
        document.getElementById('setup-result').textContent = res.success ? 'Saved. Restart dashboard.' : 'Failed.';
    } catch (e) {
        document.getElementById('setup-result').textContent = `Error: ${e.message}`;
    }
}

window.saveSetup = saveSetup;
