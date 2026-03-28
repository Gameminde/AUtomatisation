import { createStudioHelpers } from "./helpers.js";
import { createStudioRender } from "./render.js";

export async function initStudio(ctx) {
  const studioState = ctx.state.studioState;
  const helpers = createStudioHelpers(ctx);
  const render = createStudioRender(ctx, helpers);
  const $ = ctx.$;
  const tr = ctx.tr;
  const fail = ctx.fail;

  render.setCallbacks({
    refreshStudioPanels,
    renderStudioList,
    studioActions,
    studioBlank,
    studioOpen,
    setLibraryOpen,
  });

  bindStudioStatic();
  await reloadStudio();

  function bindStudioStatic() {
    syncLibraryUi();
    $("#cf-studio-new-draft")?.addEventListener("click", () => {
      setLibraryOpen(false);
      studioBlank(true);
    });
    $("#cf-studio-library-toggle")?.addEventListener("click", () => setLibraryOpen(!studioState.libraryOpen));
    $("#cf-studio-library-close")?.addEventListener("click", () => setLibraryOpen(false));
    $("#cf-studio-library-backdrop")?.addEventListener("click", () => setLibraryOpen(false));
    $("#cf-studio-search")?.addEventListener("input", (event) => {
      studioState.search = String(event.target.value || "").trim().toLowerCase();
      renderStudioList();
    });
    $("#cf-studio-schedule")?.addEventListener("input", refreshStudioPanels);
    document.querySelectorAll("#cf-studio-library-tabs [data-tab]").forEach((button) => button.addEventListener("click", () => {
      studioState.tab = button.dataset.tab || "drafts";
      document.querySelectorAll("#cf-studio-library-tabs [data-tab]").forEach((node) => node.classList.toggle("is-active", node === button));
      renderStudioList();
    }));
    $("#cf-studio-generate")?.addEventListener("click", studioGenerate);
    $("#cf-studio-regenerate")?.addEventListener("click", studioRegenerate);
    $("#cf-studio-primary-action")?.addEventListener("click", studioPrimary);
    $("#cf-studio-secondary-action")?.addEventListener("click", studioSecondary);
    $("#cf-studio-tertiary-action")?.addEventListener("click", studioTertiary);
    $("#cf-brief-toggle")?.addEventListener("click", () => {
      const toggle = $("#cf-brief-toggle");
      const advanced = $("#cf-brief-advanced");
      if (toggle && advanced) {
        toggle.classList.toggle("is-open");
        advanced.classList.toggle("is-open");
        toggle.querySelector(".cf-brief-toggle-text").textContent = advanced.classList.contains("is-open") ? tr("Fewer options") : tr("More options");
      }
    });
    ["format", "platform", "language", "tone", "niche", "goal", "hook-style"].forEach((id) => helpers.studioField(id)?.addEventListener("change", studioBriefChanged));
    ["audience", "pillar", "topic", "angle", "proof", "cta", "visual", "must-include", "avoid", "source", "regenerate-note"].forEach((id) => helpers.studioField(id)?.addEventListener("input", studioBriefChanged));
    ["topic", "angle", "proof", "source", "regenerate-note"].forEach((id) => {
      const element = helpers.studioField(id);
      if (element) {
        element.addEventListener("input", () => helpers.studioCharCount(element));
        helpers.studioCharCount(element);
      }
    });
    window.addEventListener("resize", syncLibraryUi);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && studioState.libraryOpen) setLibraryOpen(false);
    });
  }

  function syncLibraryUi() {
    const shell = $(".cf-studio-shell");
    const backdrop = $("#cf-studio-library-backdrop");
    const toggle = $("#cf-studio-library-toggle");
    const overlayMode = window.innerWidth > 1080;
    const open = overlayMode ? !!studioState.libraryOpen : true;
    if (shell) shell.dataset.libraryOpen = open ? "true" : "false";
    if (backdrop) backdrop.hidden = !(overlayMode && studioState.libraryOpen);
    if (toggle) toggle.setAttribute("aria-expanded", String(open));
  }

  function setLibraryOpen(next) {
    studioState.libraryOpen = !!next;
    syncLibraryUi();
  }

  async function withLoading(fn) {
    if (ctx.state.studioLoading) return;
    ctx.state.studioLoading = true;
    const buttons = ["#cf-studio-generate", "#cf-studio-regenerate", "#cf-studio-primary-action", "#cf-studio-secondary-action"];
    const saved = buttons.map((selector) => {
      const button = $(selector);
      if (!button) return null;
      const text = button.textContent;
      button.disabled = true;
      button.textContent = tr("Working...");
      return { button, text };
    }).filter(Boolean);
    try {
      await fn();
    } finally {
      ctx.state.studioLoading = false;
      saved.forEach(({ button, text }) => {
        button.disabled = false;
        button.textContent = text;
      });
      studioActions();
    }
  }

  async function reloadStudio(preferredId, force) {
    try {
      const bootstrap = await ctx.loadBootstrap(!!force);
      const studio = bootstrap.studio || {};
      studioState.profile = studio.profile || {};
      studioState.pages = (studio.pages || {}).pages || [];
      studioState.status = studio.status || {};
      studioState.presets = { niches: (studio.presets || {}).niches || [] };
      studioState.collections = {
        drafts: (studio.drafts || []).map(helpers.studioNorm),
        review: (studio.pending || []).map(helpers.studioNorm),
        scheduled: (studio.scheduled || []).map((row) => ({ ...row, platforms: helpers.studioPlatformValueFromRaw(row.platforms) })),
        published: (studio.published || []).map((row) => ({ ...row, platforms: helpers.studioPlatformValueFromRaw(row.platforms) })),
      };
      helpers.studioSeedBriefDefaults();
      const active = helpers.studioActivePage();
      const workspaceCopy = !active
        ? tr("Connect a Facebook page in Channels before publishing from Studio.")
        : tr("Shape the brief, preview the output, and route the best draft into review.");
      const publishState = !active
        ? tr("No active destination")
        : studioState.status && !studioState.status.can_post
          ? tr("Publishing blocked")
          : tr("Preview ready");
      $("#cf-studio-workspace-header").innerHTML = `<div class="cf-studio-work-head"><div class="cf-studio-work-copy"><div class="cf-label">${ctx.tt("Workspace")}</div><h2 class="cf-studio-work-title">${ctx.esc(active?.page_name || tr("No active destination"))}</h2><div class="cf-inline-note">${ctx.esc(workspaceCopy)}</div></div><div class="cf-studio-work-meta"><span class="cf-studio-status-chip">${ctx.esc(publishState)}</span>${!active ? `<a class="cf-btn-ghost cf-studio-head-link" href="/channels">${ctx.tt("Open Channels")}</a>` : ""}</div></div>`;
      const banners = [];
      if (!active) {
        banners.push(`<div class="cf-note-block">${ctx.tt("Connect a Facebook page in Channels before publishing from Studio.")} <a class="cf-inline-link" href="/channels">${ctx.tt("Open Channels")}</a></div>`);
      }
      if (studioState.status && !studioState.status.can_post) {
        const reason = ctx.maybeTr(studioState.status.post_reason || "Publishing is currently blocked.");
        if (!banners.some((item) => item.includes(reason))) {
          banners.push(`<div class="cf-note-block">${ctx.esc(reason)}</div>`);
        }
      }
      $("#cf-studio-banner-stack").innerHTML = banners.slice(0, 1).join("");
      syncLibraryUi();
      renderStudioList();
      const target = preferredId || studioState.current?.id || studioState.collections.drafts[0]?.id || studioState.collections.review[0]?.id || studioState.collections.scheduled[0]?.content_id || studioState.collections.published[0]?.content_id || "";
      if (target) await studioOpen(target);
      else studioBlank(false);
    } catch (error) {
      $("#cf-studio-library-list").innerHTML = fail(error.message || "Could not load Studio.");
      $("#cf-studio-editor").innerHTML = fail(error.message || "Could not load Studio.");
      $("#cf-studio-preview-card").innerHTML = fail(error.message || "Could not load Studio.");
      $("#cf-studio-brief-summary").innerHTML = fail(error.message || "Could not load Studio.");
    }
  }

  async function studioOpen(id) {
    const local = [...(studioState.collections.drafts || []), ...(studioState.collections.review || [])].find((item) => item.id === id);
    if (local) {
      studioState.current = helpers.studioNorm(local);
      render.drawStudio();
      return;
    }
    try {
      const payload = await ctx.apiCall(`/api/content/${id}`);
      const meta = helpers.studioLinkedMeta(id);
      studioState.current = helpers.studioNorm({ ...(payload.content || {}), platforms: meta?.platforms || helpers.studioPlatformValueFromRaw(helpers.studioValue("platform") || helpers.studioActivePagePlatforms()), scheduled_time: meta?.scheduled_time || payload.content?.scheduled_time, published_at: meta?.published_at || payload.content?.published_at });
    } catch (_error) {
      const meta = helpers.studioLinkedMeta(id);
      studioState.current = helpers.studioNorm({ id, content_id: id, post_type: "post", generated_text: meta?.text || "", status: meta?.published_at ? "published" : "scheduled", scheduled_time: meta?.scheduled_time, published_at: meta?.published_at, platforms: meta?.platforms || helpers.studioActivePagePlatforms() });
    }
    render.drawStudio();
  }

  function studioBlank(notify) {
    const brief = helpers.studioBriefSnapshot();
    studioState.current = {
      id: null,
      status: "draft_only",
      post_type: brief.format,
      platforms: brief.platformValue,
      content_normalized: { format: brief.format, language: brief.language, hook: "", body: "", cta: brief.cta || "", hashtags: [], image_path: "", slides: [], frames: [], points: [] },
    };
    render.drawStudio();
    if (notify) $("#cf-studio-feedback").textContent = tr("New draft started. Build the brief, run the AI preview, then decide what reaches the queue.");
  }

  function studioBriefChanged() {
    const brief = helpers.studioBriefSnapshot();
    if (studioState.current) {
      studioState.current.platforms = brief.platformValue;
      if (!studioState.current.id && !helpers.studioHasMeaningfulContent(studioState.current)) {
        studioState.current.post_type = brief.format;
        studioState.current.content_normalized = {
          ...studioState.current.content_normalized,
          format: brief.format,
          language: brief.language,
          cta: studioState.current.content_normalized?.cta || brief.cta || "",
          slides: Array.isArray(studioState.current.content_normalized?.slides) ? studioState.current.content_normalized.slides : [],
          frames: Array.isArray(studioState.current.content_normalized?.frames) ? studioState.current.content_normalized.frames : [],
          points: Array.isArray(studioState.current.content_normalized?.points) ? studioState.current.content_normalized.points : [],
        };
        render.drawStudio();
      }
    }
    if (!brief.platforms.includes(studioState.previewSurface)) studioState.previewSurface = brief.platforms[0] || "facebook";
    refreshStudioPanels();
  }

  async function studioGenerate() {
    const brief = helpers.studioBriefSnapshot();
    if (!brief.topic) return ctx.toast("Add a core topic before running the AI preview.", "error");
    await withLoading(async () => {
      const result = await ctx.apiCall("/api/studio/generate", "POST", { format: brief.format, language: brief.language, tone: brief.tone, topic: helpers.studioPromptFromBrief(brief) });
      studioState.current = helpers.studioNorm({ id: null, status: "draft_only", post_type: result.format || brief.format, platforms: brief.platformValue, content_normalized: result.content });
      render.drawStudio();
      $("#cf-studio-feedback").textContent = tr("Preview generated. Inspect the final publish surface, then save, review, schedule, or publish.");
    });
  }

  async function studioRegenerate() {
    if (!studioState.current) return ctx.toast("Generate or open a draft before iterating it.", "error");
    const brief = helpers.studioBriefSnapshot();
    await withLoading(async () => {
      if (studioState.current.id) {
        const result = await ctx.apiCall(`/api/content/${studioState.current.id}/regenerate`, "POST", { instruction: helpers.studioRegenerationInstruction(brief), tone: brief.tone });
        studioState.current = helpers.studioNorm({ ...studioState.current, post_type: result.content?.format || studioState.current.post_type, platforms: brief.platformValue, content_normalized: result.content });
        render.drawStudio();
        ctx.toast("Preview regenerated.");
        return;
      }
      await studioGenerate();
    });
  }

  async function studioPrimary() {
    const cur = studioState.current;
    if (!cur) return studioBlank(true);
    await withLoading(async () => {
      if (String(cur.status || "").toLowerCase() === "scheduled" && cur.id) {
        const when = $("#cf-studio-schedule")?.value;
        if (!when) return ctx.toast("Choose a schedule time first.", "error");
        await ctx.apiCall(`/api/content/${cur.id}/schedule`, "POST", { scheduled_time: when, platforms: helpers.studioPlatformValueFromRaw(helpers.studioValue("platform") || cur.platforms) });
        ctx.toast("Schedule updated.");
        return reloadStudio(cur.id, true);
      }
      if (String(cur.status || "").toLowerCase() === "waiting_approval" && cur.id) {
        await ctx.apiCall("/api/studio/approve", "POST", { content_id: cur.id, scheduled_time: $("#cf-studio-schedule")?.value || helpers.nextSlot(), platforms: helpers.studioPlatformValueFromRaw(helpers.studioValue("platform") || cur.platforms) });
        ctx.toast("Draft approved and scheduled.");
        return reloadStudio(cur.id, true);
      }
      await studioSave();
    });
  }

  async function studioSecondary() {
    const cur = studioState.current;
    if (!cur) return;
    await withLoading(async () => {
      const status = String(cur.status || "draft_only").toLowerCase();
      const platforms = helpers.studioPlatformsFromRaw(helpers.studioValue("platform") || cur.platforms);
      if (status === "published") {
        ctx.toast("Studio refreshed.");
        return reloadStudio(cur.id, true);
      }
      if (!cur.id) await studioSave();
      if (status === "scheduled" || status === "waiting_approval") {
        const result = await ctx.apiCall("/api/actions/publish-content", "POST", { content_id: studioState.current.id, platforms });
        ctx.toast(result.success ? "Content published." : (result.error || "Publish failed."), result.success ? "success" : "error");
        return reloadStudio(studioState.current.id, true);
      }
      await ctx.apiCall(`/api/content/${studioState.current.id}/review`, "POST", {});
      ctx.toast("Draft moved to review.");
      return reloadStudio(studioState.current.id, true);
    });
  }

  async function studioTertiary() {
    const cur = studioState.current;
    if (!cur) return studioBlank(true);
    try {
      const status = String(cur.status || "draft_only").toLowerCase();
      if (!cur.id || status === "published") return studioBlank(true);
      if (status === "scheduled") {
        await ctx.apiCall(`/api/content/${cur.id}/unschedule`, "POST", {});
        ctx.toast("Content moved back to draft.");
        return reloadStudio(cur.id, true);
      }
      if (status === "waiting_approval") {
        await ctx.apiCall(`/api/content/${cur.id}/reject`, "POST", { action: "reject", reason: "Moved to on hold from Studio" });
        ctx.toast("Draft moved to on hold.");
        return reloadStudio(cur.id, true);
      }
      studioBlank(true);
    } catch (error) {
      ctx.toast(error.message || "Could not update the draft.", "error");
    }
  }

  async function studioSave() {
    const cur = studioState.current;
    if (!cur) return;
    const content = cur.content_normalized || {};
    const format = String(content.format || cur.post_type || "post").toLowerCase();
    if (cur.id && format === "post") {
      await ctx.apiCall(`/api/content/${cur.id}`, "PUT", { hook: content.hook || "", generated_text: content.body || "", hashtags: content.hashtags || [], call_to_action: content.cta || "", image_path: content.image_path || "" });
      ctx.toast("Draft updated.");
      return reloadStudio(cur.id, true);
    }
    const saved = await ctx.apiCall("/api/studio/save-draft", "POST", { format, language: content.language || helpers.studioValue("language") || "en", content });
    ctx.toast(cur.id ? "Saved as a new draft version." : "Draft saved.");
    studioState.current = { ...cur, id: saved.content_id || cur.id, status: saved.status || "draft_only", post_type: format, platforms: helpers.studioPlatformValueFromRaw(helpers.studioValue("platform") || cur.platforms) };
    return reloadStudio(studioState.current.id, true);
  }

  function refreshStudioPanels() {
    render.refreshStudioPanels();
  }

  function renderStudioList() {
    render.renderStudioList();
  }

  function studioActions() {
    render.studioActions();
  }
}
