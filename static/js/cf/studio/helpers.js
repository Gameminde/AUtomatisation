export function createStudioHelpers(ctx) {
  const studioState = ctx.state.studioState;
  const $ = ctx.$;
  const esc = ctx.esc;
  const tr = ctx.tr;
  const tt = ctx.tt;
  const empty = ctx.empty;
  const dateTime = ctx.dateTime;

  function studioField(id) {
    return $(`#cf-studio-${id}`);
  }

  function studioValue(id) {
    return String(studioField(id)?.value || "").trim();
  }

  function studioTextHtml(value) {
    return esc(String(value || "")).replace(/\n/g, "<br>");
  }

  function studioTagList(value) {
    return String(value || "").split(/[,\n]+/).map((tag) => tag.trim()).filter(Boolean).map((tag) => tag.startsWith("#") ? tag : `#${tag}`);
  }

  function studioPlatformsFromRaw(raw) {
    return [...new Set((Array.isArray(raw) ? raw : String(raw || "").replace(/[\[\]'"]/g, "").split(",")).map((item) => String(item || "").trim().toLowerCase()).filter((item) => item === "facebook" || item === "instagram"))];
  }

  function studioPlatformValueFromRaw(raw) {
    const platforms = studioPlatformsFromRaw(raw);
    return (platforms.length ? platforms : ["facebook"]).join(",");
  }

  function studioPlatformLabel(platforms) {
    const list = Array.isArray(platforms) ? platforms : studioPlatformsFromRaw(platforms);
    if (!list.length) return tr("Facebook");
    if (list.length === 2) return tr("Facebook + Instagram");
    return list[0] === "instagram" ? tr("Instagram") : tr("Facebook");
  }

  function studioActivePage() {
    return studioState.pages.find((pageRow) => pageRow.status === "active") || studioState.pages[0] || null;
  }

  function studioActivePagePlatforms() {
    const active = studioActivePage();
    return active?.instagram_account_id ? "facebook,instagram" : "facebook";
  }

  function studioImageSource(cur) {
    const path = String(cur?.content_normalized?.image_path || "").trim();
    return cur?.id && path ? `/api/content/${cur.id}/image` : "";
  }

  function studioInitials(label) {
    const words = String(label || "CF").trim().split(/\s+/).filter(Boolean);
    return words.slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join("") || "CF";
  }

  function studioHasMeaningfulContent(cur) {
    const content = cur?.content_normalized || {};
    return !!String(content.hook || content.body || content.caption || "").trim() || !!(content.slides || []).length || !!(content.frames || []).length || !!(content.points || []).length;
  }

  function studioCharCount(element) {
    if (!element) return;
    let counter = element.parentElement.querySelector(".cf-char-count");
    if (!counter) {
      counter = document.createElement("span");
      counter.className = "cf-char-count";
      element.parentElement.appendChild(counter);
    }
    const length = element.value.length;
    counter.textContent = length > 0 ? `${length}` : "";
  }

  function studioHydrateNicheSelect() {
    const select = $("#cf-studio-niche");
    if (!select) return;
    const previous = select.value || String(studioState.profile?.niche_preset || "");
    select.innerHTML = [`<option value="">${tt("General creator")}</option>`, ...(studioState.presets.niches || []).map((niche) => `<option value="${esc(niche.id)}">${esc(niche.label)}</option>`)].join("");
    if ((studioState.presets.niches || []).some((niche) => niche.id === previous)) select.value = previous;
  }

  function nextSlot() {
    const date = new Date();
    date.setMinutes(0, 0, 0);
    date.setHours(date.getHours() + 1);
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
  }

  function localDateTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
  }

  function studioSeedBriefDefaults() {
    studioHydrateNicheSelect();
    if ($("#cf-studio-language")) $("#cf-studio-language").value = String(studioState.profile.content_language || "en").toLowerCase();
    if ($("#cf-studio-tone")) $("#cf-studio-tone").value = String(studioState.profile.content_tone || "professional").toLowerCase();
    if ($("#cf-studio-platform")) $("#cf-studio-platform").value = studioPlatformValueFromRaw(studioState.current?.platforms || studioActivePagePlatforms());
    if ($("#cf-studio-niche") && !$("#cf-studio-niche").value && studioState.profile?.niche_preset) $("#cf-studio-niche").value = studioState.profile.niche_preset;
    if ($("#cf-studio-schedule") && !$("#cf-studio-schedule").value) $("#cf-studio-schedule").value = nextSlot();
    const timezoneHint = $("#cf-studio-tz-hint");
    if (timezoneHint) {
      try {
        timezoneHint.textContent = Intl.DateTimeFormat().resolvedOptions().timeZone;
      } catch (_error) {
        timezoneHint.textContent = "";
      }
    }
  }

  function studioBriefSnapshot() {
    const nicheId = studioValue("niche");
    const niche = (studioState.presets.niches || []).find((item) => item.id === nicheId) || null;
    const platforms = studioPlatformsFromRaw(studioValue("platform") || studioState.current?.platforms || studioActivePagePlatforms());
    return {
      format: String(studioValue("format") || studioState.current?.post_type || "post").toLowerCase(),
      language: String(studioValue("language") || studioState.current?.content_normalized?.language || "en").toLowerCase(),
      tone: String(studioValue("tone") || studioState.profile.content_tone || "professional").toLowerCase(),
      platformValue: studioPlatformValueFromRaw(platforms),
      platforms,
      platformLabel: studioPlatformLabel(platforms),
      nicheId: niche?.id || "",
      nicheLabel: niche?.label || tr("General creator"),
      nicheKeywords: niche?.keywords || [],
      goal: studioValue("goal") || "engage",
      hookStyle: studioValue("hook-style") || "bold statement",
      audience: studioValue("audience"),
      pillar: studioValue("pillar"),
      topic: studioValue("topic"),
      angle: studioValue("angle"),
      proof: studioValue("proof"),
      cta: studioValue("cta"),
      visual: studioValue("visual"),
      mustInclude: studioValue("must-include"),
      avoid: studioValue("avoid"),
      source: studioValue("source"),
      regenerateNote: studioValue("regenerate-note"),
    };
  }

  function studioPromptFromBrief(brief) {
    return [
      `Create a ${ctx.titleCase(brief.format)} designed for ${brief.platformLabel}.`,
      brief.topic ? `Core topic: ${brief.topic}` : "",
      `Goal: ${ctx.titleCase(brief.goal)}`,
      `Hook style: ${ctx.titleCase(brief.hookStyle)}`,
      brief.angle ? `Angle: ${brief.angle}` : "",
      brief.audience ? `Audience: ${brief.audience}` : "",
      brief.pillar ? `Content pillar: ${brief.pillar}` : "",
      `Niche: ${brief.nicheLabel}`,
      brief.nicheKeywords.length ? `Niche keywords: ${brief.nicheKeywords.join(", ")}` : "",
      brief.proof ? `Proof points: ${brief.proof}` : "",
      brief.cta ? `Preferred CTA: ${brief.cta}` : "",
      brief.visual ? `Visual direction: ${brief.visual}` : "",
      brief.mustInclude ? `Must include: ${brief.mustInclude}` : "",
      brief.avoid ? `Avoid: ${brief.avoid}` : "",
      brief.source ? `Source or context: ${brief.source}` : "",
      "The output should feel native to the platform, creator-ready, and specific enough to publish after light editing.",
    ].filter(Boolean).join("\n");
  }

  function studioRegenerationInstruction(brief) {
    return [
      brief.regenerateNote || "",
      `Re-shape this draft for ${brief.platformLabel}.`,
      `Goal: ${ctx.titleCase(brief.goal)}.`,
      `Hook style: ${ctx.titleCase(brief.hookStyle)}.`,
      brief.angle ? `Lean into this angle: ${brief.angle}` : "",
      brief.proof ? `Keep these proof points visible: ${brief.proof}` : "",
      brief.cta ? `Use or sharpen this CTA: ${brief.cta}` : "",
      brief.visual ? `Respect this visual direction: ${brief.visual}` : "",
      brief.mustInclude ? `Must include: ${brief.mustInclude}` : "",
      brief.avoid ? `Avoid: ${brief.avoid}` : "",
    ].filter(Boolean).join("\n");
  }

  function studioNorm(row) {
    const base = ctx.cloneData(row) || {};
    const format = String(base.post_type || base.content_normalized?.format || "post").toLowerCase();
    let content = ctx.cloneData(base.content_normalized);
    if (!content) {
      if (format === "carousel") {
        const parsed = ctx.safeJson(base.generated_text);
        content = { format, language: String(parsed.language || "en").toLowerCase(), caption: parsed.caption || "", hashtags: parsed.hashtags || base.hashtags || [], slides: parsed.slides || [] };
      } else if (format === "story_sequence") {
        const parsed = ctx.safeJson(base.generated_text);
        content = { format, language: String(parsed.language || "en").toLowerCase(), frames: parsed.frames || [], hashtags: parsed.hashtags || base.hashtags || [] };
      } else if (format === "reel_script") {
        const parsed = ctx.safeJson(base.generated_text);
        content = { format, language: String(parsed.language || "en").toLowerCase(), hook: parsed.hook || base.hook || "", points: parsed.points || [], cta: parsed.cta || base.call_to_action || "", hashtags: parsed.hashtags || base.hashtags || [] };
      } else {
        content = { format: "post", language: String(base.language || base.target_audience || "en").toLowerCase(), hook: base.hook || "", body: typeof base.generated_text === "string" ? base.generated_text : "", cta: base.call_to_action || "", hashtags: base.hashtags || [], image_path: base.image_path || "" };
      }
    }
    content.language = String(content.language || "en").toLowerCase();
    content.hashtags = Array.isArray(content.hashtags) ? content.hashtags : [];
    content.slides = Array.isArray(content.slides) ? content.slides : [];
    content.frames = Array.isArray(content.frames) ? content.frames : [];
    content.points = Array.isArray(content.points) ? content.points : [];
    return { ...base, id: base.id || base.content_id || null, post_type: format, platforms: studioPlatformValueFromRaw(base.platforms || studioActivePagePlatforms()), content_normalized: content };
  }

  function studioItemText(item) {
    const content = item.content_normalized || {};
    if (content.format === "carousel") return String(content.caption || content.slides?.[0]?.headline || content.slides?.[0]?.body || "").trim() || tr("Open this carousel to inspect the full slide sequence.");
    if (content.format === "story_sequence") return String(content.frames?.[0]?.text || "").trim() || tr("Open this story sequence to inspect each frame.");
    if (content.format === "reel_script") return String(content.hook || content.points?.[0] || "").trim() || tr("Open this reel script to inspect the talking points.");
    return String(item.preview_text || content.hook || content.body || item.generated_text || item.text || "").trim() || tr("Open this record to inspect the full draft.");
  }

  function studioItems() {
    const list = studioState.collections[studioState.tab] || [];
    return !studioState.search ? list : list.filter((item) => JSON.stringify(item).toLowerCase().includes(studioState.search));
  }

  function studioListTitle(item) {
    if (item.page_name) return item.page_name;
    if (item.post_type) return ctx.titleCase(item.post_type);
    if (item.content_id && item.status === "scheduled") return tr("Scheduled slot");
    if (item.content_id && item.published_at) return tr("Published post");
    return tr("Content");
  }

  function studioStatusLabel(value) {
    const normalized = String(value || "").toLowerCase();
    if (normalized === "draft_only") return tr("Draft");
    if (normalized === "waiting_approval") return tr("Needs review");
    if (normalized === "scheduled") return tr("Scheduled");
    if (normalized === "published") return tr("Published");
    return tr(ctx.titleCase(normalized || studioState.tab));
  }

  function studioLinkedMeta(id) {
    return [...(studioState.collections.scheduled || []), ...(studioState.collections.published || [])].find((item) => item.content_id === id || item.id === id) || null;
  }

  return {
    studioState,
    studioField,
    studioValue,
    studioTextHtml,
    studioTagList,
    studioPlatformsFromRaw,
    studioPlatformValueFromRaw,
    studioPlatformLabel,
    studioActivePage,
    studioActivePagePlatforms,
    studioImageSource,
    studioInitials,
    studioHasMeaningfulContent,
    studioCharCount,
    studioHydrateNicheSelect,
    studioSeedBriefDefaults,
    studioBriefSnapshot,
    studioPromptFromBrief,
    studioRegenerationInstruction,
    studioNorm,
    studioItemText,
    studioItems,
    studioListTitle,
    studioStatusLabel,
    studioLinkedMeta,
    nextSlot,
    localDateTime,
    empty,
    dateTime,
  };
}
