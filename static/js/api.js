/**
 * API helper for Content Factory v2.
 * Keeps authenticated requests on the same-origin session-cookie path
 * expected by SaaS V1.
 */

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    return '';
}

async function apiFetch(url, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    const csrfToken = getCsrfToken();
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;
    headers['X-Requested-With'] = headers['X-Requested-With'] || 'XMLHttpRequest';
    return fetch(url, Object.assign({}, options, { headers, credentials: 'same-origin' }));
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
