export function createStudioRender(ctx, helpers) {
  const studioState = helpers.studioState;
  const $ = ctx.$;
  const esc = ctx.esc;
  const tr = ctx.tr;
  const tt = ctx.tt;
  const empty = ctx.empty;

  let refreshStudioPanels = () => {};
  let renderStudioList = () => {};
  let studioActions = () => {};
  let studioBlank = () => {};
  let studioOpen = async () => {};
  let setLibraryOpen = () => {};

  function setCallbacks(callbacks) {
    refreshStudioPanels = callbacks.refreshStudioPanels || refreshStudioPanels;
    renderStudioList = callbacks.renderStudioList || renderStudioList;
    studioActions = callbacks.studioActions || studioActions;
    studioBlank = callbacks.studioBlank || studioBlank;
    studioOpen = callbacks.studioOpen || studioOpen;
    setLibraryOpen = callbacks.setLibraryOpen || setLibraryOpen;
  }

  function studioFormatLabel(format) {
    const normalized = String(format || "post").toLowerCase();
    if (normalized === "carousel") return tr("Carousel");
    if (normalized === "story_sequence") return tr("Story sequence");
    if (normalized === "reel_script") return tr("Reel script");
    return tr("Post");
  }

  function studioGoalLabel(goal) {
    const normalized = String(goal || "engage").toLowerCase();
    if (normalized === "educate") return tr("Educate");
    if (normalized === "authority") return tr("Build authority");
    if (normalized === "community") return tr("Spark community");
    if (normalized === "promote") return tr("Promote offer");
    return tr("Engage");
  }

  function studioToneLabel(tone) {
    const normalized = String(tone || "professional").toLowerCase();
    if (normalized === "casual") return tr("Casual");
    if (normalized === "educational") return tr("Educational");
    if (normalized === "humorous") return tr("Humorous");
    return tr("Professional");
  }

  function studioHookLabel(style) {
    const normalized = String(style || "bold statement").toLowerCase();
    if (normalized === "question") return tr("Question");
    if (normalized === "story") return tr("Story");
    if (normalized === "checklist") return tr("Checklist");
    if (normalized === "contrarian") return tr("Contrarian angle");
    return tr("Bold statement");
  }

  function wireStudioInputs() {
    const content = studioState.current?.content_normalized;
    if (!content) return;
    const refresh = () => refreshStudioPanels();
    $("#cf-editor-hook")?.addEventListener("input", (event) => { content.hook = event.target.value; refresh(); });
    $("#cf-editor-body")?.addEventListener("input", (event) => { content.body = event.target.value; refresh(); });
    $("#cf-editor-cta")?.addEventListener("input", (event) => { content.cta = event.target.value; refresh(); });
    $("#cf-editor-image")?.addEventListener("input", (event) => { content.image_path = event.target.value; refresh(); });
    $("#cf-editor-caption")?.addEventListener("input", (event) => { content.caption = event.target.value; refresh(); });
    $("#cf-editor-tags")?.addEventListener("input", (event) => { content.hashtags = helpers.studioTagList(event.target.value); refresh(); });
    document.querySelectorAll("[data-slide-head]").forEach((node) => node.addEventListener("input", (event) => {
      const index = Number(event.target.dataset.slideHead);
      content.slides[index] = { ...(content.slides[index] || {}), headline: event.target.value };
      refresh();
    }));
    document.querySelectorAll("[data-slide-body]").forEach((node) => node.addEventListener("input", (event) => {
      const index = Number(event.target.dataset.slideBody);
      content.slides[index] = { ...(content.slides[index] || {}), body: event.target.value };
      refresh();
    }));
    document.querySelectorAll("[data-slide-visual]").forEach((node) => node.addEventListener("input", (event) => {
      const index = Number(event.target.dataset.slideVisual);
      content.slides[index] = { ...(content.slides[index] || {}), visual_suggestion: event.target.value };
      refresh();
    }));
    document.querySelectorAll("[data-frame-text]").forEach((node) => node.addEventListener("input", (event) => {
      const index = Number(event.target.dataset.frameText);
      content.frames[index] = { ...(content.frames[index] || {}), text: event.target.value };
      refresh();
    }));
    document.querySelectorAll("[data-frame-visual]").forEach((node) => node.addEventListener("input", (event) => {
      const index = Number(event.target.dataset.frameVisual);
      content.frames[index] = { ...(content.frames[index] || {}), visual_suggestion: event.target.value };
      refresh();
    }));
    document.querySelectorAll("[data-reel-point]").forEach((node) => node.addEventListener("input", (event) => {
      const index = Number(event.target.dataset.reelPoint);
      content.points[index] = event.target.value;
      refresh();
    }));
  }

  function studioEditorMarkup(cur) {
    const content = cur?.content_normalized || {};
    const format = String(content.format || cur?.post_type || "post").toLowerCase();
    if (format === "carousel") {
      return `<div class="cf-settings-grid"><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-editor-caption">${tt("Caption")}</label><textarea id="cf-editor-caption" class="cf-textarea cf-textarea-sm" rows="4">${esc(content.caption || "")}</textarea></div><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-editor-tags">${tt("Hashtags")}</label><input id="cf-editor-tags" class="cf-input" type="text" value="${esc((content.hashtags || []).join(", "))}"></div></div><div class="cf-structured-list">${(content.slides || []).length ? content.slides.map((slide, index) => `<article class="cf-structured-item"><div class="cf-row-main"><div class="cf-label">${tt("Slide {index}", { index: index + 1 })}</div><span class="cf-inline-note">${esc(slide.visual_suggestion || tr("No visual note"))}</span></div><input class="cf-input" data-slide-head="${index}" type="text" value="${esc(slide.headline || "")}" placeholder="${esc(tr("Headline"))}"><textarea class="cf-textarea cf-textarea-sm" data-slide-body="${index}" rows="3" placeholder="${esc(tr("Slide body"))}">${esc(slide.body || "")}</textarea><input class="cf-input" data-slide-visual="${index}" type="text" value="${esc(slide.visual_suggestion || "")}" placeholder="${esc(tr("Visual suggestion"))}"></article>`).join("") : `<div class="cf-note-block">${tt("This carousel has no slides yet. Run the AI preview or iterate the draft to build the slide flow.")}</div>`}</div>`;
    }
    if (format === "story_sequence") {
      return `<div class="cf-structured-list">${(content.frames || []).length ? content.frames.map((frame, index) => `<article class="cf-structured-item"><div class="cf-row-main"><div class="cf-label">${tt("Frame {index}", { index: index + 1 })}</div><span class="cf-inline-note">${esc(frame.visual_suggestion || tr("No visual note"))}</span></div><textarea class="cf-textarea cf-textarea-sm" data-frame-text="${index}" rows="4" placeholder="${esc(tr("Frame text"))}">${esc(frame.text || "")}</textarea><input class="cf-input" data-frame-visual="${index}" type="text" value="${esc(frame.visual_suggestion || "")}" placeholder="${esc(tr("Visual suggestion"))}"></article>`).join("") : `<div class="cf-note-block">${tt("This format is preview-first. Save the draft if you want to keep it as an exportable story plan.")}</div>`}</div>`;
    }
    if (format === "reel_script") {
      return `<div class="cf-settings-grid"><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-editor-hook">${tt("Opening hook")}</label><input id="cf-editor-hook" class="cf-input" type="text" value="${esc(content.hook || "")}"></div><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-editor-cta">${tt("Closing CTA")}</label><input id="cf-editor-cta" class="cf-input" type="text" value="${esc(content.cta || "")}"></div><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-editor-tags">${tt("Hashtags")}</label><input id="cf-editor-tags" class="cf-input" type="text" value="${esc((content.hashtags || []).join(", "))}"></div></div><div class="cf-structured-list">${(content.points || []).length ? content.points.map((point, index) => `<article class="cf-structured-item"><div class="cf-label">${tt("Talking point {index}", { index: index + 1 })}</div><textarea class="cf-textarea cf-textarea-sm" data-reel-point="${index}" rows="3" placeholder="${esc(tr("Talking point"))}">${esc(point || "")}</textarea></article>`).join("") : `<div class="cf-note-block">${tt("This reel script has no talking points yet. Run the AI preview or iterate it with a tighter brief.")}</div>`}</div>`;
    }
    return `<div class="cf-settings-grid"><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-editor-hook">${tt("Hook")}</label><input id="cf-editor-hook" class="cf-input" type="text" value="${esc(content.hook || "")}"></div><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-editor-body">${tt("Body")}</label><textarea id="cf-editor-body" class="cf-textarea" rows="8">${esc(content.body || "")}</textarea></div><div class="cf-field"><label class="cf-field-label" for="cf-editor-cta">${tt("CTA")}</label><input id="cf-editor-cta" class="cf-input" type="text" value="${esc(content.cta || "")}"></div><div class="cf-field"><label class="cf-field-label" for="cf-editor-tags">${tt("Hashtags")}</label><input id="cf-editor-tags" class="cf-input" type="text" value="${esc((content.hashtags || []).join(", "))}"></div><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-editor-image">${tt("Image path")}</label><input id="cf-editor-image" class="cf-input" type="text" value="${esc(content.image_path || "")}" placeholder="${esc(tr("Optional image path for publish preview"))}"></div></div>`;
  }

  function studioSummaryMarkup(brief, cur) {
    const cards = [
      { title: tr("Publish route"), value: tr("{format} for {platform}", { format: studioFormatLabel(brief.format), platform: brief.platformLabel }), copy: `${studioGoalLabel(brief.goal)} | ${studioToneLabel(brief.tone)}` },
      { title: tr("Angle and hook direction"), value: brief.angle || studioHookLabel(brief.hookStyle), copy: brief.audience || brief.nicheLabel },
      { title: tr("Offer or CTA"), value: brief.cta || tr("Not set"), copy: brief.proof || brief.visual || tr("No proof points added yet") },
    ];
    return cards.map((item) => `<article class="cf-studio-summary-card"><div class="cf-summary-copy"><div class="cf-label">${esc(item.title)}</div><div class="cf-summary-value">${esc(item.value)}</div></div><div class="cf-inline-note">${esc(item.copy)}</div></article>`).join("");
  }

  function studioPreviewMetaMarkup(brief, cur) {
    const active = helpers.studioActivePage();
    const schedule = $("#cf-studio-schedule")?.value || (cur?.scheduled_time ? helpers.localDateTime(cur.scheduled_time) : "");
    return `<div class="cf-route-kicker">${tt("Publish route")}</div><div class="cf-route-title">${esc(tr("{destination} via {platform}", { destination: active?.page_name || tr("No active destination"), platform: brief.platformLabel }))}</div><div class="cf-studio-route-grid"><div><span class="cf-label">${tt("Schedule")}</span><strong>${esc(schedule || tr("Not scheduled"))}</strong></div><div><span class="cf-label">${tt("State")}</span><strong>${esc(cur?.id ? helpers.studioStatusLabel(cur.status || "draft_only") : tr("Unsaved preview"))}</strong></div></div>`;
  }

  function renderStudioPreviewTabs(brief) {
    const surfaces = brief.platforms.length ? brief.platforms : ["facebook"];
    if (!surfaces.includes(studioState.previewSurface)) studioState.previewSurface = surfaces[0];
    $("#cf-studio-preview-tabs").innerHTML = surfaces.map((surface) => `<button type="button" class="cf-preview-surface-toggle ${surface === studioState.previewSurface ? "is-active" : ""}" data-preview-surface="${esc(surface)}">${esc(tr(surface === "instagram" ? "Instagram preview" : "Facebook preview"))}</button>`).join("");
    document.querySelectorAll("[data-preview-surface]").forEach((button) => button.addEventListener("click", () => {
      studioState.previewSurface = button.dataset.previewSurface || surfaces[0];
      refreshStudioPanels();
    }));
  }

  function studioWarningsMarkup(brief, cur) {
    const active = helpers.studioActivePage();
    const items = [];
    if (studioState.status && !studioState.status.can_post) items.push({ kind: "warn", title: tr("Publishing blocked"), copy: studioState.status.post_reason || tr("The account is not ready to publish right now.") });
    if (brief.platforms.includes("instagram") && !active?.instagram_account_id) items.push({ kind: "warn", title: tr("Instagram missing"), copy: tr("Instagram is selected in the brief, but the active page does not have an Instagram account linked.") });
    if (brief.platforms.includes("instagram") && brief.format === "post" && !String(cur?.content_normalized?.image_path || "").trim()) items.push({ kind: "warn", title: tr("Instagram media gap"), copy: tr("Instagram post previews need an image path before the publish result will match the preview.") });
    if (brief.format === "story_sequence" || brief.format === "reel_script") items.push({ kind: "warn", title: tr("Draft-only format"), copy: tr("Story sequences and reel scripts stay export-first in V1. Save them as drafts rather than expecting auto-publish.") });
    if (cur && !cur.id) items.push({ kind: "note", title: tr("Preview only"), copy: tr("This AI result lives in the browser until you save it to the library.") });
    if (!items.length) return "";
    return `<div class="cf-warning-stack">${items.slice(0, 2).map((item) => `<article class="cf-warning-card ${esc(item.kind)}"><div class="cf-label">${esc(item.title)}</div><div>${esc(item.copy)}</div></article>`).join("")}</div>`;
  }

  function studioPreviewMediaMarkup(cur, surface) {
    const imagePath = String(cur?.content_normalized?.image_path || "").trim();
    const source = helpers.studioImageSource(cur);
    if (source) return `<figure class="cf-surface-image"><img src="${esc(source)}" alt="${esc(tr("Draft media preview"))}"><figcaption>${esc(imagePath || tr("Saved media"))}</figcaption></figure>`;
    if (!imagePath) return surface === "instagram" ? `<div class="cf-surface-image is-empty">${tt("Instagram preview is selected, but this draft does not have an image path yet.")}</div>` : "";
    return `<div class="cf-surface-image"><div class="cf-label">${tt("Media selected")}</div><div class="cf-inline-note">${esc(imagePath)}</div></div>`;
  }

  function studioPreviewMarkup(cur, surface, brief) {
    const content = cur?.content_normalized || {};
    const format = String(content.format || cur?.post_type || "post").toLowerCase();
    const active = helpers.studioActivePage();
    const pageName = active?.page_name || tr("Connected page");
    const header = `<div class="cf-surface-header"><div class="cf-surface-avatar">${esc(helpers.studioInitials(pageName))}</div><div class="cf-surface-lines"><strong>${esc(pageName)}</strong><span>${esc(tr(surface === "instagram" ? "Instagram preview" : "Facebook preview"))}</span></div><span class="cf-platform-chip">${esc(tr(surface === "instagram" ? "Instagram" : "Facebook"))}</span></div>`;
    if (format === "carousel") return `<article class="cf-social-surface"><div class="cf-preview-card">${header}<div class="cf-surface-caption">${helpers.studioTextHtml(content.caption || tr("No caption yet."))}</div><div class="cf-structured-list">${(content.slides || []).map((slide, index) => `<article class="cf-preview-slide"><div class="cf-preview-slide-index">${index + 1}</div><div class="cf-preview-slide-title">${esc(slide.headline || tr("Slide headline"))}</div><div class="cf-preview-body">${helpers.studioTextHtml(slide.body || tr("Slide body"))}</div><div class="cf-inline-note">${esc(slide.visual_suggestion || tr("No visual suggestion"))}</div></article>`).join("") || `<div class="cf-note-block">${tt("This carousel preview is empty. Run the AI preview to generate slides.")}</div>`}</div><div class="cf-preview-footer">${esc((content.hashtags || []).join(" "))}</div></div></article>`;
    if (format === "story_sequence") return `<article class="cf-social-surface"><div class="cf-preview-card">${header}<div class="cf-story-preview">${(content.frames || []).map((frame, index) => `<article class="cf-preview-slide"><div class="cf-preview-slide-index">${index + 1}</div><div class="cf-preview-body">${helpers.studioTextHtml(frame.text || tr("Frame text"))}</div><div class="cf-inline-note">${esc(frame.visual_suggestion || tr("No visual direction"))}</div></article>`).join("") || `<div class="cf-note-block">${tt("This story sequence preview is empty. Run the AI preview to generate frames.")}</div>`}</div></div></article>`;
    if (format === "reel_script") return `<article class="cf-social-surface"><div class="cf-preview-card">${header}<div class="cf-surface-caption"><strong>${esc(content.hook || tr("Reel hook"))}</strong></div><div class="cf-structured-list">${(content.points || []).map((point, index) => `<article class="cf-structured-item"><div class="cf-label">${tt("Beat {index}", { index: index + 1 })}</div><div>${esc(point || tr("Talking point"))}</div></article>`).join("") || `<div class="cf-note-block">${tt("This reel script preview is empty. Run the AI preview to generate talking points.")}</div>`}</div><div class="cf-preview-body">${esc(content.cta || tr("Add a closing CTA to tighten the script."))}</div><div class="cf-preview-footer">${esc((content.hashtags || []).join(" "))}</div></div></article>`;
    return `<article class="cf-social-surface ${surface === "instagram" ? "is-instagram" : "is-facebook"}"><div class="cf-preview-card">${header}${studioPreviewMediaMarkup(cur, surface)}<div class="cf-surface-caption"><strong>${esc(content.hook || tr("Post hook"))}</strong><div class="cf-preview-body">${helpers.studioTextHtml(content.body || tr("Body copy"))}</div>${content.cta ? `<div class="cf-surface-cta">${esc(content.cta)}</div>` : ""}</div><div class="cf-preview-footer">${esc((content.hashtags || []).join(" "))}</div><div class="cf-inline-note">${esc(tr("Prepared for {platform} in {language}.", { platform: brief.platformLabel, language: brief.language.toUpperCase() }))}</div></div></article>`;
  }

  function drawStudio() {
    const cur = studioState.current;
    if (!cur) {
      $("#cf-studio-editor").innerHTML = empty("No draft selected", "Choose an item from the library or create a new draft.");
      refreshStudioPanels();
      studioActions();
      renderStudioList();
      return;
    }
    const content = cur.content_normalized || {};
    const format = String(content.format || cur.post_type || "post").toLowerCase();
    if ($("#cf-studio-format")) $("#cf-studio-format").value = format;
    if ($("#cf-studio-language")) $("#cf-studio-language").value = String(content.language || "en").toLowerCase();
    if ($("#cf-studio-platform")) $("#cf-studio-platform").value = helpers.studioPlatformValueFromRaw(cur.platforms || helpers.studioActivePagePlatforms());
    if (!helpers.studioValue("cta") && content.cta) $("#cf-studio-cta").value = content.cta;
    if ($("#cf-studio-schedule")) $("#cf-studio-schedule").value = cur.scheduled_time ? helpers.localDateTime(cur.scheduled_time) : ($("#cf-studio-schedule").value || helpers.nextSlot());
    $("#cf-studio-editor").innerHTML = studioEditorMarkup(cur);
    wireStudioInputs();
    refreshStudioPanels();
    studioActions();
    renderStudioList();
  }

  function refreshPanels() {
    const brief = helpers.studioBriefSnapshot();
    $("#cf-studio-brief-summary").innerHTML = studioSummaryMarkup(brief, studioState.current);
    $("#cf-studio-preview-meta").innerHTML = studioPreviewMetaMarkup(brief, studioState.current);
    renderStudioPreviewTabs(brief);
    $("#cf-studio-preview-card").innerHTML = studioState.current && helpers.studioHasMeaningfulContent(studioState.current) ? studioPreviewMarkup(studioState.current, studioState.previewSurface, brief) : empty("Preview unavailable", "Run the AI preview or open a draft to inspect the final publish surface.");
    $("#cf-studio-review-meta").innerHTML = studioWarningsMarkup(brief, studioState.current);
  }

  function renderList() {
    const items = helpers.studioItems();
    const libraryCount = $("#cf-studio-library-count");
    if (libraryCount) libraryCount.textContent = String(items.length);
    $("#cf-studio-library-list").innerHTML = items.length ? items.map((item) => {
      const id = item.content_id || item.id;
      const active = studioState.current?.id === id;
      const stamp = item.generated_at || item.scheduled_time || item.published_at || item.time;
      const route = helpers.studioPlatformLabel(item.platforms);
      const format = studioFormatLabel(item.post_type || item.content_normalized?.format || "post");
      return `<button type="button" class="cf-draft-item ${active ? "is-active" : ""}" data-studio-open="${esc(id || "")}"><div class="cf-library-card-top"><span class="cf-draft-format">${esc(helpers.studioStatusLabel(item.status || studioState.tab))}</span><span class="cf-inline-note">${esc(helpers.dateTime(stamp))}</span></div><strong class="cf-library-card-title">${esc(helpers.studioListTitle(item))}</strong><div class="cf-library-card-snippet">${esc(helpers.studioItemText(item))}</div><div class="cf-library-card-bottom"><span>${esc(route || tr("Facebook"))}</span><span>${esc(format)}</span></div></button>`;
    }).join("") : empty("No items here", "This library segment is currently empty.");
    document.querySelectorAll("[data-studio-open]").forEach((button) => button.addEventListener("click", async () => {
      await studioOpen(button.dataset.studioOpen);
      setLibraryOpen(false);
      renderList();
    }));
  }

  function renderActions() {
    const status = String(studioState.current?.status || "draft_only").toLowerCase();
    const format = String(studioState.current?.post_type || studioState.current?.content_normalized?.format || "post").toLowerCase();
    $("#cf-studio-primary-action").disabled = false;
    $("#cf-studio-secondary-action").disabled = false;
    $("#cf-studio-tertiary-action").disabled = false;
    if (status === "scheduled") {
      $("#cf-studio-primary-action").textContent = tr("Update Schedule");
      $("#cf-studio-secondary-action").textContent = tr("Publish Now");
      $("#cf-studio-tertiary-action").textContent = tr("Unschedule");
      return;
    }
    if (status === "waiting_approval") {
      $("#cf-studio-primary-action").textContent = tr("Approve & Schedule");
      $("#cf-studio-secondary-action").textContent = tr("Publish Now");
      $("#cf-studio-tertiary-action").textContent = tr("Move to On Hold");
      return;
    }
    if (status === "published") {
      $("#cf-studio-primary-action").textContent = tr("Save Draft Version");
      $("#cf-studio-secondary-action").textContent = tr("Refresh");
      $("#cf-studio-tertiary-action").textContent = tr("Clear");
      return;
    }
    $("#cf-studio-primary-action").textContent = tr("Save Draft");
    $("#cf-studio-secondary-action").textContent = (format === "story_sequence" || format === "reel_script") ? tr("Export Only") : tr("Send to Review");
    $("#cf-studio-tertiary-action").textContent = tr("Clear Draft");
    $("#cf-studio-secondary-action").disabled = format === "story_sequence" || format === "reel_script";
  }

  return {
    setCallbacks,
    wireStudioInputs,
    drawStudio,
    refreshStudioPanels: refreshPanels,
    renderStudioList: renderList,
    studioActions: renderActions,
  };
}
