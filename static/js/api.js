/**
 * API helper for Content Factory v2.
 * Injects X-API-Key header from meta tag or localStorage.
 */

function getApiKey() {
    const meta = document.querySelector('meta[name="dashboard-api-key"]');
    if (meta && meta.content) return meta.content;
    return localStorage.getItem('dashboard_api_key') || '';
}

async function apiFetch(url, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    const apiKey = getApiKey();
    if (apiKey) headers['X-API-Key'] = apiKey;
    return fetch(url, Object.assign({}, options, { headers }));
}

async function apiCall(endpoint, method = 'GET', data = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (data) opts.body = JSON.stringify(data);
    const res = await apiFetch(endpoint, opts);
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'API Error');
    return json;
}

window.apiFetch = apiFetch;
window.apiCall = apiCall;
