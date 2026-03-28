export function createRuntime(page) {
  const state = {
    page: page || "",
    i18n: window.CF_I18N || {},
    currentLocale: String(window.CF_LOCALE || document.body?.dataset.systemLang || "EN").toUpperCase(),
    bootstrapPromise: null,
    bootstrapState: null,
    studioLoading: false,
    studioState: {
      profile: null,
      pages: [],
      status: null,
      presets: { niches: [] },
      collections: { drafts: [], review: [], scheduled: [], published: [] },
      tab: "drafts",
      search: "",
      current: null,
      previewSurface: "facebook",
      libraryOpen: false,
    },
  };

  const ctx = {
    state,
    rehydrateCurrentPage: null,
    $: (selector, root) => (root || document).querySelector(selector),
    esc(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    },
    localeCode(locale) {
      return { EN: "en", FR: "fr", AR: "ar" }[String(locale || state.currentLocale).toUpperCase()] || "en";
    },
    tr(text, params) {
      const source = String(text ?? "");
      const dict = state.i18n[String(state.currentLocale || "EN").toUpperCase()] || {};
      let translated = Object.prototype.hasOwnProperty.call(dict, source) ? dict[source] : source;
      Object.entries(params || {}).forEach(([key, value]) => {
        translated = translated.replaceAll(`{${key}}`, String(value ?? ""));
      });
      return translated;
    },
    maybeTr(value) {
      const source = String(value ?? "");
      const dict = state.i18n[String(state.currentLocale || "EN").toUpperCase()] || {};
      return Object.prototype.hasOwnProperty.call(dict, source) ? dict[source] : source;
    },
    tt(text, params) {
      return ctx.esc(ctx.tr(text, params));
    },
    shortDate(value) {
      if (!value) return ctx.tr("Not set");
      const date = new Date(value);
      return Number.isNaN(date.getTime())
        ? ctx.maybeTr(value)
        : date.toLocaleDateString(ctx.localeCode(), { year: "numeric", month: "short", day: "numeric" });
    },
    dateTime(value) {
      if (!value) return ctx.tr("Not set");
      const date = new Date(value);
      return Number.isNaN(date.getTime())
        ? ctx.maybeTr(value)
        : date.toLocaleString(ctx.localeCode(), { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    },
    tone(value) {
      const normalized = String(value || "").toLowerCase();
      if (["ok", "healthy", "active", "connected", "published", "ready"].includes(normalized)) return "ok";
      if (["warn", "warning", "watch", "degraded", "inactive", "paused", "expiring"].includes(normalized)) return "warn";
      return "err";
    },
    empty(title, copy, href, label) {
      return `<div class="cf-empty-state"><div class="cf-empty-title">${ctx.tt(title)}</div><div class="cf-empty-copy">${ctx.tt(copy)}</div>${href && label ? `<a class="cf-btn" href="${ctx.esc(href)}">${ctx.tt(label)}</a>` : ""}</div>`;
    },
    fail(copy) {
      return `<div class="cf-error-state"><div class="cf-error-title">${ctx.tt("Something failed to load")}</div><div class="cf-error-copy">${ctx.esc(ctx.maybeTr(copy))}</div></div>`;
    },
    card(label, value, copy) {
      const renderedValue = ctx.maybeTr(value);
      const valueText = renderedValue == null ? "" : String(renderedValue);
      const valueClass = /^[-+]?[\d\s.,/%]+$/.test(valueText) ? "is-metric" : "is-copy";
      return `<article class="cf-card cf-stat-card"><div class="cf-label">${ctx.tt(label)}</div><span class="cf-stat-value ${valueClass}">${ctx.esc(valueText)}</span><div class="cf-stat-delta">${ctx.esc(ctx.maybeTr(copy))}</div></article>`;
    },
    line(label, value, forcedTone) {
      return `<div class="cf-row-main"><span>${ctx.tt(label)}</span><span class="cf-status ${ctx.esc(forcedTone || ctx.tone(value))}"><span class="cf-status-dot"></span><span>${ctx.esc(ctx.maybeTr(value))}</span></span></div>`;
    },
    toastHost() {
      if (!ctx.$(".cf-toast-host")) {
        const node = document.createElement("div");
        node.className = "cf-toast-host";
        document.body.appendChild(node);
      }
    },
    toast(message, kind) {
      const host = ctx.$(".cf-toast-host");
      if (!host) return;
      const node = document.createElement("div");
      node.className = `cf-toast ${kind || "success"}`;
      node.textContent = ctx.maybeTr(message);
      host.appendChild(node);
      requestAnimationFrame(() => node.classList.add("is-visible"));
      setTimeout(() => {
        node.classList.remove("is-visible");
        setTimeout(() => node.remove(), 220);
      }, 2400);
    },
    timeline(selector, events, copy) {
      const node = ctx.$(selector);
      if (!node) return;
      if (!(events || []).length) {
        node.innerHTML = ctx.empty("No events yet", copy);
        return;
      }
      node.innerHTML = events.map((event) => `<article class="cf-timeline-item"><div class="cf-row-main"><strong>${ctx.esc(ctx.maybeTr(event.message || event.type || "Event"))}</strong><span class="cf-pill">${ctx.esc(ctx.maybeTr(event.type || "event"))}</span></div><div class="cf-inline-note">${ctx.esc(ctx.dateTime(event.at))}</div></article>`).join("");
    },
    blockList(selector, items, emptyCopy, renderItem) {
      const node = ctx.$(selector);
      if (!node) return;
      if (!(items || []).length) {
        node.innerHTML = ctx.empty("Nothing to show", emptyCopy);
        return;
      }
      node.innerHTML = items.map(renderItem).join("");
    },
    apiCall(...args) {
      return window.apiCall(...args);
    },
    async loadBootstrap(force) {
      if (!force && state.bootstrapState) return state.bootstrapState;
      if (!force && state.bootstrapPromise) return state.bootstrapPromise;
      const suffix = force ? "&refresh=1" : "";
      state.bootstrapPromise = ctx.apiCall(`/api/bootstrap?page=${encodeURIComponent(state.page)}${suffix}`)
        .then((payload) => {
          state.bootstrapState = payload || {};
          return state.bootstrapState;
        })
        .finally(() => {
          if (!state.bootstrapState) state.bootstrapPromise = null;
        });
      return state.bootstrapPromise;
    },
    async refreshBootstrap() {
      state.bootstrapState = null;
      state.bootstrapPromise = null;
      return ctx.loadBootstrap(true);
    },
    bootstrapSection(name) {
      return (state.bootstrapState || {})[name] || {};
    },
    safeJson(value) {
      try {
        const parsed = JSON.parse(String(value || "{}"));
        return parsed && typeof parsed === "object" ? parsed : {};
      } catch (_error) {
        return {};
      }
    },
    cloneData(value) {
      try {
        return JSON.parse(JSON.stringify(value));
      } catch (_error) {
        return value;
      }
    },
    titleCase(value) {
      return String(value || "")
        .split(/[_\s]+/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
    },
  };

  return ctx;
}
