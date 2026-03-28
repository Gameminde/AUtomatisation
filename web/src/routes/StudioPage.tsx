import { ChangeEvent, Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiCall, BootstrapResponse } from "../lib/api";
import { BootPayload } from "../lib/boot";
import { Translator } from "../lib/i18n";
import {
  StudioBrief,
  StudioItem,
  StudioPageRow,
  StudioTab,
  activePage,
  activePagePlatforms,
  briefPrompt,
  formatLabel,
  goalLabel,
  hasMeaningfulContent,
  hookLabel,
  initials,
  itemText,
  listTitle,
  localDateTime,
  nextSlot,
  normalizeStudioItem,
  platformLabel,
  platformValueFromRaw,
  platformsFromRaw,
  regenerationPrompt,
  statusLabel,
  tagList,
  toneLabel,
} from "../lib/studio";
import { EmptyState, ErrorState } from "../ui/States";
import { useToast } from "../ui/ToastProvider";

type StudioProps = {
  boot: BootPayload;
  translator: Translator;
  loading: boolean;
  error: string | null;
  payload: BootstrapResponse | null;
  refresh: (force?: boolean) => Promise<BootstrapResponse | null>;
};

type StudioProfile = {
  content_language?: string;
  content_tone?: string;
  niche_preset?: string;
};

type StudioCollections = Record<StudioTab, StudioItem[]>;

function readNicheMeta(niches: Array<Record<string, unknown>>, nicheId: string, translator: Translator) {
  const niche = niches.find((item) => String(item.id || "") === nicheId);
  return {
    label: String(niche?.label || translator.tr("General creator")),
    keywords: Array.isArray(niche?.keywords) ? (niche?.keywords as string[]) : [],
  };
}

function renderLines(text: string) {
  const lines = String(text || "").split("\n");
  return lines.map((line, index) => (
    <Fragment key={`${line}-${index}`}>
      {line}
      {index < lines.length - 1 ? <br /> : null}
    </Fragment>
  ));
}

function joinLines(lines: string[]): string {
  return lines.filter((line) => String(line || "").trim()).join("\n");
}

function createBlankDraft(brief: StudioBrief): StudioItem {
  return {
    id: null,
    status: "draft_only",
    post_type: brief.format,
    platforms: brief.platform,
    content_normalized: {
      format: brief.format,
      language: brief.language,
      hook: "",
      body: "",
      cta: brief.cta || "",
      caption: "",
      hashtags: [],
      image_path: "",
      slides: [],
      frames: [],
      points: [],
    },
  };
}

function buildStudioCollections(studio: Record<string, unknown>, fallbackPlatforms: string): StudioCollections {
  return {
    drafts: Array.isArray(studio.drafts) ? studio.drafts.map((row) => normalizeStudioItem(row as Record<string, unknown>, fallbackPlatforms)) : [],
    review: Array.isArray(studio.pending) ? studio.pending.map((row) => normalizeStudioItem(row as Record<string, unknown>, fallbackPlatforms)) : [],
    scheduled: Array.isArray(studio.scheduled) ? studio.scheduled.map((row) => normalizeStudioItem(row as Record<string, unknown>, fallbackPlatforms)) : [],
    published: Array.isArray(studio.published) ? studio.published.map((row) => normalizeStudioItem(row as Record<string, unknown>, fallbackPlatforms)) : [],
  };
}

function PreviewBody({ current, surface, translator, pageName, briefPlatformLabel }: { current: StudioItem; surface: string; translator: Translator; pageName: string; briefPlatformLabel: string }) {
  const content = current.content_normalized;
  const format = String(content.format || current.post_type || "post").toLowerCase();
  const imageSource = current.id && String(content.image_path || "").trim() ? `/api/content/${current.id}/image` : "";

  const header = (
    <div className="cf-surface-header">
      <div className="cf-surface-avatar">{initials(pageName)}</div>
      <div className="cf-surface-lines">
        <strong>{pageName}</strong>
        <span>{translator.tr(surface === "instagram" ? "Instagram preview" : "Facebook preview")}</span>
      </div>
      <span className="cf-platform-chip">{translator.tr(surface === "instagram" ? "Instagram" : "Facebook")}</span>
    </div>
  );

  if (format === "carousel") {
    return (
      <article className="cf-social-surface">
        <div className="cf-preview-card">
          {header}
          <div className="cf-surface-caption">{renderLines(String(content.caption || translator.tr("No caption yet.")))}</div>
          <div className="cf-structured-list">
            {content.slides.length ? content.slides.map((slide, index) => (
              <article key={`slide-${index}`} className="cf-preview-slide">
                <div className="cf-preview-slide-index">{index + 1}</div>
                <div className="cf-preview-slide-title">{slide.headline || translator.tr("Slide headline")}</div>
                <div className="cf-preview-body">{renderLines(String(slide.body || translator.tr("Slide body")))}</div>
                <div className="cf-inline-note">{slide.visual_suggestion || translator.tr("No visual suggestion")}</div>
              </article>
            )) : (
              <div className="cf-note-block">{translator.tr("This carousel preview is empty. Run the AI preview to generate slides.")}</div>
            )}
          </div>
          <div className="cf-preview-footer">{content.hashtags.join(" ")}</div>
        </div>
      </article>
    );
  }

  if (format === "story_sequence") {
    return (
      <article className="cf-social-surface">
        <div className="cf-preview-card">
          {header}
          <div className="cf-story-preview">
            {content.frames.length ? content.frames.map((frame, index) => (
              <article key={`frame-${index}`} className="cf-preview-slide">
                <div className="cf-preview-slide-index">{index + 1}</div>
                <div className="cf-preview-body">{renderLines(String(frame.text || translator.tr("Frame text")))}</div>
                <div className="cf-inline-note">{frame.visual_suggestion || translator.tr("No visual direction")}</div>
              </article>
            )) : (
              <div className="cf-note-block">{translator.tr("This story sequence preview is empty. Run the AI preview to generate frames.")}</div>
            )}
          </div>
        </div>
      </article>
    );
  }

  if (format === "reel_script") {
    return (
      <article className="cf-social-surface">
        <div className="cf-preview-card">
          {header}
          <div className="cf-surface-caption">
            <strong>{content.hook || translator.tr("Reel hook")}</strong>
          </div>
          <div className="cf-structured-list">
            {content.points.length ? content.points.map((point, index) => (
              <article key={`beat-${index}`} className="cf-structured-item">
                <div className="cf-label">{translator.tr("Beat {index}", { index: index + 1 })}</div>
                <div>{point || translator.tr("Talking point")}</div>
              </article>
            )) : (
              <div className="cf-note-block">{translator.tr("This reel script preview is empty. Run the AI preview to generate talking points.")}</div>
            )}
          </div>
          <div className="cf-preview-body">{content.cta || translator.tr("Add a closing CTA to tighten the script.")}</div>
          <div className="cf-preview-footer">{content.hashtags.join(" ")}</div>
        </div>
      </article>
    );
  }

  return (
    <article className={`cf-social-surface ${surface === "instagram" ? "is-instagram" : "is-facebook"}`}>
      <div className="cf-preview-card">
        {header}
        {imageSource ? (
          <figure className="cf-surface-image">
            <img src={imageSource} alt={translator.tr("Draft media preview")} />
            <figcaption>{content.image_path || translator.tr("Saved media")}</figcaption>
          </figure>
        ) : surface === "instagram" ? (
          <div className="cf-surface-image is-empty">{translator.tr("Instagram preview is selected, but this draft does not have an image path yet.")}</div>
        ) : null}
        <div className="cf-surface-caption">
          <strong>{content.hook || translator.tr("Post hook")}</strong>
          <div className="cf-preview-body">{renderLines(String(content.body || translator.tr("Body copy")))}</div>
          {content.cta ? <div className="cf-surface-cta">{content.cta}</div> : null}
        </div>
        <div className="cf-preview-footer">{content.hashtags.join(" ")}</div>
        <div className="cf-inline-note">{translator.tr("Prepared for {platform} in {language}.", { platform: briefPlatformLabel, language: content.language.toUpperCase() })}</div>
      </div>
    </article>
  );
}

export function StudioPage({ boot, translator, loading, error, payload, refresh }: StudioProps) {
  const { push } = useToast();
  const [profile, setProfile] = useState<Record<string, unknown>>({});
  const [pages, setPages] = useState<StudioPageRow[]>([]);
  const [status, setStatus] = useState<Record<string, unknown>>({});
  const [niches, setNiches] = useState<Array<Record<string, unknown>>>([]);
  const [collections, setCollections] = useState<StudioCollections>({ drafts: [], review: [], scheduled: [], published: [] });
  const [tab, setTab] = useState<StudioTab>("drafts");
  const [search, setSearch] = useState("");
  const [current, setCurrent] = useState<StudioItem | null>(null);
  const [previewSurface, setPreviewSurface] = useState<"facebook" | "instagram">("facebook");
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(translator.tr("Set the brief, run an AI preview, then decide what the agent should save, review, schedule, or publish."));
  const [brief, setBrief] = useState<StudioBrief>({
    format: "post",
    platform: "facebook",
    language: "en",
    tone: "professional",
    niche: "",
    goal: "educate",
    hookStyle: "bold statement",
    audience: "",
    pillar: "",
    topic: "",
    angle: "",
    proof: "",
    cta: "",
    visual: "",
    mustInclude: "",
    avoid: "",
    source: "",
    regenerateNote: "",
    schedule: nextSlot(),
  });
  const [windowWidth, setWindowWidth] = useState(() => window.innerWidth);
  const briefRef = useRef(brief);
  const currentIdRef = useRef<string | null>(current?.id ?? null);

  const overlayLibrary = windowWidth > 1080;

  useEffect(() => {
    briefRef.current = brief;
  }, [brief]);

  useEffect(() => {
    currentIdRef.current = current?.id ?? null;
  }, [current?.id]);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const hydrateFromPayload = useCallback(async (nextPayload: BootstrapResponse | null, preferredId?: string | null) => {
    const studio = (nextPayload?.studio || {}) as Record<string, unknown>;
    const profileData = (studio.profile || {}) as StudioProfile;
    const nextPages = Array.isArray((studio.pages as Record<string, unknown> | undefined)?.pages)
      ? (((studio.pages as Record<string, unknown>).pages) as StudioPageRow[])
      : [];
    const fallbackPlatforms = activePagePlatforms(nextPages);
    const nextCollections = buildStudioCollections(studio, fallbackPlatforms);

    setProfile(profileData as Record<string, unknown>);
    setPages(nextPages);
    setStatus((studio.status || {}) as Record<string, unknown>);
    setNiches(Array.isArray((studio.presets as Record<string, unknown> | undefined)?.niches) ? (((studio.presets as Record<string, unknown>).niches) as Array<Record<string, unknown>>) : []);
    setCollections(nextCollections);
    setBrief((currentBrief) => ({
      ...currentBrief,
      language: String(currentBrief.language || profileData.content_language || "en").toLowerCase(),
      tone: String(currentBrief.tone || profileData.content_tone || "professional").toLowerCase(),
      niche: String(currentBrief.niche || profileData.niche_preset || ""),
      platform: currentBrief.platform || fallbackPlatforms,
      schedule: currentBrief.schedule || nextSlot(),
    }));

    const target = preferredId
      || currentIdRef.current
      || nextCollections.drafts[0]?.id
      || nextCollections.review[0]?.id
      || nextCollections.scheduled[0]?.content_id
      || nextCollections.published[0]?.content_id
      || null;

    if (!target) {
      const baseBrief = briefRef.current;
      setCurrent(createBlankDraft({
        ...baseBrief,
        platform: fallbackPlatforms,
      }));
      return;
    }

    const local = [...nextCollections.drafts, ...nextCollections.review].find((item) => item.id === target);
    if (local) {
      setCurrent(local);
      setBrief((currentBrief) => ({
        ...currentBrief,
        format: local.post_type,
        language: local.content_normalized.language || currentBrief.language,
        platform: platformValueFromRaw(local.platforms || fallbackPlatforms),
        cta: currentBrief.cta || local.content_normalized.cta || "",
        schedule: local.scheduled_time ? localDateTime(local.scheduled_time) : currentBrief.schedule,
      }));
      return;
    }

    const meta = [...nextCollections.scheduled, ...nextCollections.published].find((item) => item.content_id === target || item.id === target) || null;
    try {
      const response = await apiCall<{ success: boolean; content: Record<string, unknown> }>(`/api/content/${target}`);
      const normalized = normalizeStudioItem(
        {
          ...response.content,
          platforms: meta?.platforms || fallbackPlatforms,
          scheduled_time: meta?.scheduled_time,
          published_at: meta?.published_at,
        },
        fallbackPlatforms,
      );
      setCurrent(normalized);
      setBrief((currentBrief) => ({
        ...currentBrief,
        format: normalized.post_type,
        language: normalized.content_normalized.language || currentBrief.language,
        platform: platformValueFromRaw(normalized.platforms || fallbackPlatforms),
        cta: currentBrief.cta || normalized.content_normalized.cta || "",
        schedule: normalized.scheduled_time ? localDateTime(normalized.scheduled_time) : currentBrief.schedule,
      }));
    } catch (_error) {
      setCurrent(normalizeStudioItem({
        id: target,
        content_id: target,
        post_type: "post",
        generated_text: meta?.text || "",
        status: meta?.published_at ? "published" : "scheduled",
        scheduled_time: meta?.scheduled_time,
        published_at: meta?.published_at,
        platforms: meta?.platforms || fallbackPlatforms,
      }, fallbackPlatforms));
    }
  }, []);

  useEffect(() => {
    void hydrateFromPayload(payload);
  }, [hydrateFromPayload, payload]);

  useEffect(() => {
    const surfaces = platformsFromRaw(brief.platform);
    if (!surfaces.includes(previewSurface)) {
      setPreviewSurface((surfaces[0] || "facebook") as "facebook" | "instagram");
    }
  }, [brief.platform, previewSurface]);

  useEffect(() => {
    if (current && !current.id && !hasMeaningfulContent(current)) {
      const nextCta = current.content_normalized.cta || brief.cta || "";
      const requiresSync =
        current.post_type !== brief.format
        || current.platforms !== brief.platform
        || current.content_normalized.format !== brief.format
        || current.content_normalized.language !== brief.language
        || (current.content_normalized.cta || "") !== nextCta;

      if (!requiresSync) {
        return;
      }

      setCurrent({
        ...current,
        post_type: brief.format,
        platforms: brief.platform,
        content_normalized: {
          ...current.content_normalized,
          format: brief.format,
          language: brief.language,
          cta: nextCta,
        },
      });
    }
  }, [brief.cta, brief.format, brief.language, brief.platform, current]);

  const filteredItems = useMemo(() => {
    const source = collections[tab] || [];
    if (!search.trim()) return source;
    const lowered = search.trim().toLowerCase();
    return source.filter((item) => JSON.stringify(item).toLowerCase().includes(lowered));
  }, [collections, search, tab]);

  const page = activePage(pages);
  const platformOptions = platformsFromRaw(brief.platform);
  const nicheMeta = readNicheMeta(niches, brief.niche, translator);
  const activeStatus = !page
    ? translator.tr("No active destination")
    : status.can_post === false
      ? translator.tr("Publishing blocked")
      : translator.tr("Preview ready");

  const openItem = useCallback(async (id: string) => {
    await hydrateFromPayload(payload, id);
    setLibraryOpen(false);
  }, [hydrateFromPayload, payload]);

  const reloadStudio = useCallback(async (preferredId?: string | null) => {
    const nextPayload = await refresh(true);
    await hydrateFromPayload(nextPayload, preferredId);
  }, [hydrateFromPayload, refresh]);

  const setBriefField = useCallback((field: keyof StudioBrief, value: string) => {
    setBrief((currentBrief) => ({ ...currentBrief, [field]: value }));
  }, []);

  const setCurrentContent = useCallback((updates: Partial<StudioItem["content_normalized"]>) => {
    setCurrent((currentItem) => {
      if (!currentItem) return currentItem;
      return {
        ...currentItem,
        content_normalized: {
          ...currentItem.content_normalized,
          ...updates,
        },
      };
    });
  }, []);

  const setCurrentTextField = useCallback((field: keyof StudioItem["content_normalized"], value: string) => {
    setCurrentContent({ [field]: value } as Partial<StudioItem["content_normalized"]>);
  }, [setCurrentContent]);

  const setCurrentHashtags = useCallback((value: string) => {
    setCurrentContent({ hashtags: tagList(value) });
  }, [setCurrentContent]);

  const setCurrentSlidesFromText = useCallback((value: string) => {
    const slides = value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [headline, ...bodyParts] = line.split("|");
        return {
          headline: String(headline || "").trim(),
          body: String(bodyParts.join("|") || "").trim(),
          visual_suggestion: "",
        };
      });
    setCurrentContent({ slides });
  }, [setCurrentContent]);

  const setCurrentFramesFromText = useCallback((value: string) => {
    const frames = value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => ({ text: line, visual_suggestion: "" }));
    setCurrentContent({ frames });
  }, [setCurrentContent]);

  const setCurrentPointsFromText = useCallback((value: string) => {
    const points = value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    setCurrentContent({ points });
  }, [setCurrentContent]);

  const withBusy = useCallback(async (work: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    try {
      await work();
    } finally {
      setBusy(false);
    }
  }, [busy]);

  const saveDraft = useCallback(async (): Promise<string | null> => {
    if (!current) return null;
    const content = current.content_normalized;
    const format = String(content.format || current.post_type || "post").toLowerCase() as StudioBrief["format"];
    if (current.id && format === "post") {
      await apiCall(`/api/content/${current.id}`, "PUT", {
        hook: content.hook || "",
        generated_text: content.body || "",
        hashtags: content.hashtags || [],
        call_to_action: content.cta || "",
        image_path: content.image_path || "",
      });
      push(translator.tr("Draft updated."));
      await reloadStudio(current.id);
      return current.id;
    }

    const saved = await apiCall<{ success: boolean; content_id: string }>(
      "/api/studio/save-draft",
      "POST",
      {
        format,
        language: content.language || brief.language || "en",
        content,
      },
    );
    push(translator.tr(current.id ? "Saved as a new draft version." : "Draft saved."));
    await reloadStudio(saved.content_id);
    return saved.content_id;
  }, [brief.language, current, push, reloadStudio, translator]);

  const handleGenerate = useCallback(async () => {
    if (!brief.topic.trim()) {
      push(translator.tr("Add a core topic before running the AI preview."), "error");
      return;
    }
    await withBusy(async () => {
      const result = await apiCall<{ success: boolean; format: StudioBrief["format"]; content: StudioItem["content_normalized"] }>(
        "/api/studio/generate",
        "POST",
        {
          format: brief.format,
          language: brief.language,
          tone: brief.tone,
          topic: briefPrompt(brief, nicheMeta.label, nicheMeta.keywords, translator),
        },
      );
      setCurrent({
        id: null,
        status: "draft_only",
        post_type: result.format || brief.format,
        platforms: brief.platform,
        content_normalized: {
          ...result.content,
          format: result.format || brief.format,
          hashtags: Array.isArray(result.content.hashtags) ? result.content.hashtags : [],
          slides: Array.isArray(result.content.slides) ? result.content.slides : [],
          frames: Array.isArray(result.content.frames) ? result.content.frames : [],
          points: Array.isArray(result.content.points) ? result.content.points : [],
        },
      });
      setFeedback(translator.tr("Preview generated. Inspect the final publish surface, then save, review, schedule, or publish."));
    });
  }, [brief, nicheMeta.keywords, nicheMeta.label, push, translator, withBusy]);

  const handleRegenerate = useCallback(async () => {
    if (!current) {
      push(translator.tr("Generate or open a draft before iterating it."), "error");
      return;
    }

    await withBusy(async () => {
      if (current.id) {
        const result = await apiCall<{ success: boolean; content: StudioItem["content_normalized"] }>(
          `/api/content/${current.id}/regenerate`,
          "POST",
          { instruction: regenerationPrompt(brief), tone: brief.tone },
        );
        setCurrent({
          ...current,
          content_normalized: {
            ...result.content,
            format: (result.content.format || current.post_type) as StudioBrief["format"],
            hashtags: Array.isArray(result.content.hashtags) ? result.content.hashtags : [],
            slides: Array.isArray(result.content.slides) ? result.content.slides : [],
            frames: Array.isArray(result.content.frames) ? result.content.frames : [],
            points: Array.isArray(result.content.points) ? result.content.points : [],
          },
        });
        push(translator.tr("Preview regenerated."));
        return;
      }
      await handleGenerate();
    });
  }, [brief, current, handleGenerate, push, translator, withBusy]);

  const handlePrimaryAction = useCallback(async () => {
    if (!current) {
      setCurrent(createBlankDraft(brief));
      return;
    }
    await withBusy(async () => {
      const currentStatus = String(current.status || "").toLowerCase();
      if (currentStatus === "scheduled" && current.id) {
        if (!brief.schedule) {
          push(translator.tr("Choose a schedule time first."), "error");
          return;
        }
        await apiCall(`/api/content/${current.id}/schedule`, "POST", {
          scheduled_time: brief.schedule,
          platforms: platformValueFromRaw(brief.platform || current.platforms),
        });
        push(translator.tr("Schedule updated."));
        await reloadStudio(current.id);
        return;
      }
      if (currentStatus === "waiting_approval" && current.id) {
        await apiCall("/api/studio/approve", "POST", {
          content_id: current.id,
          scheduled_time: brief.schedule || nextSlot(),
          platforms: platformValueFromRaw(brief.platform || current.platforms),
        });
        push(translator.tr("Draft approved and scheduled."));
        await reloadStudio(current.id);
        return;
      }
      await saveDraft();
    });
  }, [brief, current, push, reloadStudio, saveDraft, translator, withBusy]);

  const handleSecondaryAction = useCallback(async () => {
    if (!current) return;
    await withBusy(async () => {
      const currentStatus = String(current.status || "draft_only").toLowerCase();
      const platforms = platformsFromRaw(brief.platform || current.platforms);
      if (currentStatus === "published") {
        push(translator.tr("Studio refreshed."));
        await reloadStudio(current.id);
        return;
      }
      const ensuredId = current.id || await saveDraft();
      if (!ensuredId) return;
      if (currentStatus === "scheduled" || currentStatus === "waiting_approval") {
        const result = await apiCall<{ success: boolean; error?: string }>("/api/actions/publish-content", "POST", {
          content_id: ensuredId,
          platforms,
        });
        push(result.success ? translator.tr("Content published.") : translator.maybeTr(result.error || "Publish failed."), result.success ? "success" : "error");
        await reloadStudio(ensuredId);
        return;
      }
      await apiCall(`/api/content/${ensuredId}/review`, "POST", {});
      push(translator.tr("Draft moved to review."));
      await reloadStudio(ensuredId);
    });
  }, [brief.platform, current, push, reloadStudio, saveDraft, translator, withBusy]);

  const handleTertiaryAction = useCallback(async () => {
    if (!current) {
      setCurrent(createBlankDraft(brief));
      return;
    }
    await withBusy(async () => {
      const currentStatus = String(current.status || "draft_only").toLowerCase();
      if (!current.id || currentStatus === "published") {
        setCurrent(createBlankDraft(brief));
        return;
      }
      if (currentStatus === "scheduled") {
        await apiCall(`/api/content/${current.id}/unschedule`, "POST", {});
        push(translator.tr("Content moved back to draft."));
        await reloadStudio(current.id);
        return;
      }
      if (currentStatus === "waiting_approval") {
        await apiCall(`/api/content/${current.id}/reject`, "POST", {
          action: "reject",
          reason: "Moved to on hold from Studio",
        });
        push(translator.tr("Draft moved to on hold."));
        await reloadStudio(current.id);
        return;
      }
      setCurrent(createBlankDraft(brief));
    });
  }, [brief, current, push, reloadStudio, translator, withBusy]);

  const currentStatus = String(current?.status || "draft_only").toLowerCase();
  const currentFormat = String(current?.post_type || current?.content_normalized.format || "post").toLowerCase();
  const primaryLabel = currentStatus === "scheduled"
    ? translator.tr("Update Schedule")
    : currentStatus === "waiting_approval"
      ? translator.tr("Approve & Schedule")
      : currentStatus === "published"
        ? translator.tr("Save Draft Version")
        : translator.tr("Save Draft");
  const secondaryLabel = currentStatus === "published"
    ? translator.tr("Refresh")
    : currentStatus === "scheduled" || currentStatus === "waiting_approval"
      ? translator.tr("Publish Now")
      : translator.tr("Send to Review");
  const tertiaryLabel = currentStatus === "scheduled"
    ? translator.tr("Unschedule")
    : currentStatus === "waiting_approval"
      ? translator.tr("Move to On Hold")
      : translator.tr("Clear Draft");
  const secondaryDisabled = currentFormat === "story_sequence" || currentFormat === "reel_script";

  const insightCards = [
    {
      title: translator.tr("Publish route"),
      value: translator.tr("{format} for {platform}", {
        format: formatLabel(brief.format, translator),
        platform: platformLabel(brief.platform, translator),
      }),
      copy: `${goalLabel(brief.goal, translator)} | ${toneLabel(brief.tone, translator)}`,
    },
    {
      title: translator.tr("Angle and hook direction"),
      value: brief.angle || hookLabel(brief.hookStyle, translator),
      copy: brief.audience || nicheMeta.label,
    },
    {
      title: translator.tr("Offer or CTA"),
      value: brief.cta || translator.tr("Not set"),
      copy: brief.proof || brief.visual || translator.tr("No proof points added yet"),
    },
  ];

  const warningItems = [
    status.can_post === false ? {
      kind: "warn",
      title: translator.tr("Publishing blocked"),
      copy: translator.maybeTr(String(status.post_reason || "The account is not ready to publish right now.")),
    } : null,
    platformOptions.includes("instagram") && !page?.instagram_account_id ? {
      kind: "warn",
      title: translator.tr("Instagram missing"),
      copy: translator.tr("Instagram is selected in the brief, but the active page does not have an Instagram account linked."),
    } : null,
    platformOptions.includes("instagram") && brief.format === "post" && !String(current?.content_normalized.image_path || "").trim() ? {
      kind: "warn",
      title: translator.tr("Instagram media gap"),
      copy: translator.tr("Instagram post previews need an image path before the publish result will match the preview."),
    } : null,
    (brief.format === "story_sequence" || brief.format === "reel_script") ? {
      kind: "warn",
      title: translator.tr("Draft-only format"),
      copy: translator.tr("Story sequences and reel scripts stay export-first in V1. Save them as drafts rather than expecting auto-publish."),
    } : null,
    current && !current.id ? {
      kind: "note",
      title: translator.tr("Preview only"),
      copy: translator.tr("This AI result lives in the browser until you save it to the library."),
    } : null,
  ].filter(Boolean) as Array<{ kind: string; title: string; copy: string }>;

  const workspaceCopy = !page
    ? translator.tr("Connect a Facebook page in Channels before publishing from Studio.")
    : translator.tr("Shape the brief, preview the output, and route the best draft into review.");

  const listEmptyCopy = translator.tr("This library segment is currently empty.");
  const currentContent = current?.content_normalized || null;
  const editorHashtags = currentContent ? (currentContent.hashtags || []).join(", ") : "";
  const carouselSlidesText = currentContent
    ? joinLines((currentContent.slides || []).map((slide) => [slide.headline, slide.body].filter(Boolean).join(" | ")))
    : "";
  const storyFramesText = currentContent
    ? joinLines((currentContent.frames || []).map((frame) => String(frame.text || "")))
    : "";
  const reelPointsText = currentContent
    ? joinLines((currentContent.points || []).map((point) => String(point || "")))
    : "";

  return (
    <section className="cf-screen cf-studio-page" data-cf-studio="">
      <header className="cf-page-intro cf-page-intro-actions cf-studio-page-head">
        <div>
          <h1 className="cf-page-title">{translator.tr("Design, test, and route every post")}</h1>
          <p className="cf-page-copy">{translator.tr("Shape the brief like a creator, run an AI preview, inspect the final publish surface, then decide what the agent should save, review, schedule, or publish.")}</p>
        </div>
        <div className="cf-page-intro-meta cf-studio-head-actions">
          <button type="button" className="cf-btn-ghost cf-studio-head-drawer" id="cf-studio-library-toggle" onClick={() => setLibraryOpen((currentOpen) => !currentOpen)}>
            <span>{translator.tr("Library")}</span>
            <span id="cf-studio-library-count" className="cf-studio-head-count">{filteredItems.length}</span>
          </button>
          <button
            type="button"
            className="cf-btn"
            id="cf-studio-new-draft"
            onClick={() => {
              setCurrent(createBlankDraft(brief));
              setFeedback(translator.tr("New draft started. Build the brief, run the AI preview, then decide what reaches the queue."));
              setLibraryOpen(false);
            }}
          >
            {translator.tr("New Draft")}
          </button>
        </div>
      </header>

      <section className="cf-studio-shell" data-library-open={overlayLibrary ? String(libraryOpen) : "true"} aria-label={translator.tr("Studio")}>
        {overlayLibrary && libraryOpen ? (
          <div className="cf-studio-library-backdrop" id="cf-studio-library-backdrop" onClick={() => setLibraryOpen(false)} />
        ) : null}

        <aside className="cf-card cf-studio-library-drawer" id="cf-studio-library-drawer" aria-label={translator.tr("Library")}>
          <div className="cf-studio-library-bar">
            <div className="cf-studio-rail-head">
              <div className="cf-studio-step-kicker">
                <span className="cf-step-chip">01</span>
                <span className="cf-label">{translator.tr("Library")}</span>
              </div>
              <span className="cf-inline-note">{translator.tr("Queue and draft archive")}</span>
            </div>
            <button type="button" className="cf-btn-ghost cf-studio-library-close" id="cf-studio-library-close" onClick={() => setLibraryOpen(false)}>
              {translator.tr("Close")}
            </button>
          </div>
          <div className="cf-tab-row" id="cf-studio-library-tabs">
            {([
              ["drafts", translator.tr("Drafts")],
              ["review", translator.tr("Needs review")],
              ["scheduled", translator.tr("Scheduled")],
              ["published", translator.tr("Published")],
            ] as Array<[StudioTab, string]>).map(([nextTab, label]) => (
              <button key={nextTab} type="button" className={`cf-tab ${tab === nextTab ? "is-active" : ""}`} data-tab={nextTab} onClick={() => setTab(nextTab)}>
                {label}
              </button>
            ))}
          </div>
          <div className="cf-field">
            <label className="cf-field-label" htmlFor="cf-studio-search">{translator.tr("Search")}</label>
            <input id="cf-studio-search" className="cf-input" type="search" placeholder={translator.tr("Search content")} value={search} onChange={(event) => setSearch(event.target.value)} />
          </div>
          <div id="cf-studio-library-list" className="cf-draft-list" aria-live="polite">
            {filteredItems.length ? filteredItems.map((item) => {
              const id = item.content_id || item.id || "";
              const stamp = item.generated_at || item.scheduled_time || item.published_at || "";
              return (
                <button key={id} type="button" className={`cf-draft-item ${current?.id === id ? "is-active" : ""}`} data-studio-open={id} onClick={() => void openItem(id)}>
                  <div className="cf-library-card-top">
                    <span className="cf-draft-format">{statusLabel(item.status || tab, translator)}</span>
                    <span className="cf-inline-note">{translator.dateTime(stamp)}</span>
                  </div>
                  <strong className="cf-library-card-title">{listTitle(item, translator)}</strong>
                  <div className="cf-library-card-snippet">{itemText(item, translator)}</div>
                  <div className="cf-library-card-bottom">
                    <span>{platformLabel(item.platforms, translator)}</span>
                    <span>{formatLabel(item.post_type, translator)}</span>
                  </div>
                </button>
              );
            }) : <EmptyState title={translator.tr("No items here")} copy={listEmptyCopy} />}
          </div>
        </aside>

        <div className="cf-studio-stage">
          <article className="cf-card cf-panel cf-studio-composer-card">
            <div className="cf-studio-panel-head cf-studio-panel-head-simple">
              <div className="cf-studio-panel-copy">
                <div className="cf-studio-mini-kicker">{translator.tr("Creator brief")}</div>
                <h2 className="cf-studio-panel-title">{translator.tr("Start with the post idea")}</h2>
                <p className="cf-inline-note">{translator.tr("Choose the format, set the route, write the core idea, then run the AI preview.")}</p>
              </div>
              <div className="cf-inline-actions cf-studio-brief-toolbar">
                <button type="button" className="cf-btn" id="cf-studio-generate" onClick={() => void handleGenerate()} disabled={busy}>{busy ? translator.tr("Working...") : translator.tr("Run AI Preview")}</button>
                <button type="button" className="cf-btn-ghost" id="cf-studio-regenerate" onClick={() => void handleRegenerate()} disabled={busy}>{busy ? translator.tr("Working...") : translator.tr("Iterate Preview")}</button>
              </div>
            </div>

            <div className="cf-studio-composer-grid">
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-studio-format">{translator.tr("Format")}</label>
                <select id="cf-studio-format" className="cf-select" value={brief.format} onChange={(event) => setBriefField("format", event.target.value)}>
                  <option value="post">{translator.tr("Post")}</option>
                  <option value="carousel">{translator.tr("Carousel")}</option>
                  <option value="story_sequence">{translator.tr("Story sequence")}</option>
                  <option value="reel_script">{translator.tr("Reel script")}</option>
                </select>
              </div>
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-studio-platform">{translator.tr("Publish route")}</label>
                <select id="cf-studio-platform" className="cf-select" value={brief.platform} onChange={(event) => setBriefField("platform", event.target.value)}>
                  <option value="facebook">{translator.tr("Facebook only")}</option>
                  <option value="facebook,instagram">{translator.tr("Facebook + Instagram")}</option>
                  <option value="instagram">{translator.tr("Instagram only")}</option>
                </select>
              </div>
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-studio-language">{translator.tr("Language")}</label>
                <select id="cf-studio-language" className="cf-select" value={brief.language} onChange={(event) => setBriefField("language", event.target.value)}>
                  <option value="en">{translator.tr("English")}</option>
                  <option value="fr">{translator.tr("French")}</option>
                  <option value="ar">{translator.tr("Arabic")}</option>
                </select>
              </div>
              <div className="cf-field cf-field-span">
                <label className="cf-field-label" htmlFor="cf-studio-topic">{translator.tr("Core topic")}</label>
                <textarea id="cf-studio-topic" className="cf-textarea cf-textarea-sm" rows={3} placeholder={translator.tr("Describe the main idea, claim, or lesson you want to publish.")} value={brief.topic} onChange={(event) => setBriefField("topic", event.target.value)} />
              </div>
            </div>

            <div className="cf-studio-composer-foot">
              <span className="cf-inline-note" id="cf-studio-feedback">{feedback}</span>
              <button type="button" className={`cf-brief-toggle ${advancedOpen ? "is-open" : ""}`} id="cf-brief-toggle" onClick={() => setAdvancedOpen((open) => !open)}>
                <span className="cf-brief-toggle-text">{translator.tr(advancedOpen ? "Fewer options" : "More options")}</span>
                <span className="cf-brief-toggle-icon">▾</span>
              </button>
            </div>

            <div className={`cf-brief-advanced ${advancedOpen ? "is-open" : ""}`} id="cf-brief-advanced">
              <div className="cf-studio-brief-grid">
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-studio-tone">{translator.tr("Tone")}</label>
                  <select id="cf-studio-tone" className="cf-select" value={brief.tone} onChange={(event) => setBriefField("tone", event.target.value)}>
                    <option value="professional">{translator.tr("Professional")}</option>
                    <option value="casual">{translator.tr("Casual")}</option>
                    <option value="educational">{translator.tr("Educational")}</option>
                    <option value="humorous">{translator.tr("Humorous")}</option>
                  </select>
                </div>
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-studio-goal">{translator.tr("Content goal")}</label>
                  <select id="cf-studio-goal" className="cf-select" value={brief.goal} onChange={(event) => setBriefField("goal", event.target.value)}>
                    <option value="educate">{translator.tr("Educate")}</option>
                    <option value="engage">{translator.tr("Engage")}</option>
                    <option value="authority">{translator.tr("Build authority")}</option>
                    <option value="community">{translator.tr("Spark community")}</option>
                    <option value="promote">{translator.tr("Promote offer")}</option>
                  </select>
                </div>
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-studio-hook-style">{translator.tr("Hook style")}</label>
                  <select id="cf-studio-hook-style" className="cf-select" value={brief.hookStyle} onChange={(event) => setBriefField("hookStyle", event.target.value)}>
                    <option value="bold statement">{translator.tr("Bold statement")}</option>
                    <option value="question">{translator.tr("Question")}</option>
                    <option value="story">{translator.tr("Story")}</option>
                    <option value="checklist">{translator.tr("Checklist")}</option>
                    <option value="contrarian">{translator.tr("Contrarian angle")}</option>
                  </select>
                </div>
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-studio-niche">{translator.tr("Niche")}</label>
                  <select id="cf-studio-niche" className="cf-select" value={brief.niche} onChange={(event) => setBriefField("niche", event.target.value)}>
                    <option value="">{translator.tr("General creator")}</option>
                    {niches.map((niche) => (
                      <option key={String(niche.id || "")} value={String(niche.id || "")}>
                        {String(niche.label || translator.tr("General creator"))}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-studio-audience">{translator.tr("Audience")}</label>
                  <input id="cf-studio-audience" className="cf-input" type="text" value={brief.audience} onChange={(event) => setBriefField("audience", event.target.value)} />
                </div>
                <div className="cf-field cf-field-span">
                  <label className="cf-field-label" htmlFor="cf-studio-cta">{translator.tr("Offer or CTA")}</label>
                  <textarea id="cf-studio-cta" className="cf-textarea cf-textarea-sm" rows={2} value={brief.cta} onChange={(event) => setBriefField("cta", event.target.value)} />
                </div>
                <div className="cf-field cf-field-span">
                  <label className="cf-field-label" htmlFor="cf-studio-proof">{translator.tr("Proof points and key points")}</label>
                  <textarea id="cf-studio-proof" className="cf-textarea cf-textarea-sm" rows={3} value={brief.proof} onChange={(event) => setBriefField("proof", event.target.value)} />
                </div>
                <div className="cf-field cf-field-span">
                  <label className="cf-field-label" htmlFor="cf-studio-regenerate-note">{translator.tr("Iteration note")}</label>
                  <textarea id="cf-studio-regenerate-note" className="cf-textarea cf-textarea-sm" rows={2} value={brief.regenerateNote} onChange={(event) => setBriefField("regenerateNote", event.target.value)} />
                </div>
              </div>
            </div>
          </article>

          <div className="cf-studio-canvas-simple">
            <section className="cf-studio-preview-column">
              <article className="cf-card cf-panel cf-studio-preview-shell">
                <div className="cf-studio-preview-hero">
                  <div className="cf-studio-preview-hero-copy">
                    <div className="cf-studio-mini-kicker">{translator.tr("Final preview")}</div>
                    <div id="cf-studio-workspace-header" className="cf-studio-workspace-head" aria-live="polite">
                      <div className="cf-studio-work-head">
                        <div className="cf-studio-work-copy">
                          <div className="cf-label">{translator.tr("Workspace")}</div>
                          <h2 className="cf-studio-work-title">{page?.page_name || translator.tr("No active destination")}</h2>
                          <div className="cf-inline-note">{workspaceCopy}</div>
                        </div>
                        <div className="cf-studio-work-meta">
                          <span className="cf-studio-status-chip">{activeStatus}</span>
                          {!page ? <a className="cf-btn-ghost cf-studio-head-link" href={boot.urls.channels}>{translator.tr("Open Channels")}</a> : null}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div id="cf-studio-preview-tabs" className="cf-studio-preview-tabs" aria-live="polite">
                    {(platformOptions.length ? platformOptions : ["facebook"]).map((surface) => (
                      <button key={surface} type="button" className={`cf-preview-surface-toggle ${previewSurface === surface ? "is-active" : ""}`} data-preview-surface={surface} onClick={() => setPreviewSurface(surface as "facebook" | "instagram")}>
                        {translator.tr(surface === "instagram" ? "Instagram preview" : "Facebook preview")}
                      </button>
                    ))}
                  </div>
                </div>

                <div id="cf-studio-banner-stack" className="cf-studio-banner-stack" aria-live="polite">
                  {!page ? (
                    <div className="cf-note-block">
                      {translator.tr("Connect a Facebook page in Channels before publishing from Studio.")}{" "}
                      <a className="cf-inline-link" href={boot.urls.channels}>{translator.tr("Open Channels")}</a>
                    </div>
                  ) : null}
                </div>

                <div id="cf-studio-review-meta" className="cf-studio-preview-notes">
                  {warningItems.length ? (
                    <div className="cf-warning-stack">
                      {warningItems.slice(0, 2).map((warning) => (
                        <article key={`${warning.kind}-${warning.title}`} className={`cf-warning-card ${warning.kind}`}>
                          <div className="cf-label">{warning.title}</div>
                          <div>{warning.copy}</div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    translator.tr("Run an AI preview to inspect the final caption, slides, and route before the agent touches Facebook or Instagram.")
                  )}
                </div>

                <div id="cf-studio-preview-card" className="cf-preview-card" aria-live="polite">
                  {current && hasMeaningfulContent(current) ? (
                    <PreviewBody current={current} surface={previewSurface} translator={translator} pageName={page?.page_name || translator.tr("Connected page")} briefPlatformLabel={platformLabel(brief.platform, translator)} />
                  ) : (
                    <EmptyState title={translator.tr("Preview unavailable")} copy={translator.tr("Run the AI preview or open a draft to inspect the final publish surface.")} />
                  )}
                </div>
              </article>

              <article className="cf-card cf-panel cf-studio-editor-card">
                <div className="cf-studio-panel-head cf-studio-panel-head-simple">
                  <div className="cf-studio-panel-copy">
                    <div className="cf-studio-mini-kicker">{translator.tr("Editor")}</div>
                    <h2 className="cf-studio-panel-title">{translator.tr("Adjust the final draft")}</h2>
                    <p className="cf-inline-note">{translator.tr("Refine the actual output before it goes to review or publish.")}</p>
                  </div>
                </div>
                <div id="cf-studio-editor" aria-live="polite">
                  {current ? (
                    <div className="cf-studio-workbench">
                      {(currentFormat === "post" || currentFormat === "reel_script") ? (
                        <div className="cf-field">
                          <label className="cf-field-label" htmlFor="cf-studio-editor-hook">{translator.tr(currentFormat === "reel_script" ? "Reel hook" : "Hook")}</label>
                          <textarea id="cf-studio-editor-hook" className="cf-textarea cf-textarea-sm" rows={2} value={currentContent?.hook || ""} onChange={(event) => setCurrentTextField("hook", event.target.value)} />
                        </div>
                      ) : null}

                      {currentFormat === "post" ? (
                        <div className="cf-field">
                          <label className="cf-field-label" htmlFor="cf-studio-editor-body">{translator.tr("Body")}</label>
                          <textarea id="cf-studio-editor-body" className="cf-textarea" rows={6} value={currentContent?.body || ""} onChange={(event) => setCurrentTextField("body", event.target.value)} />
                        </div>
                      ) : null}

                      {currentFormat === "carousel" ? (
                        <>
                          <div className="cf-field">
                            <label className="cf-field-label" htmlFor="cf-studio-editor-caption">{translator.tr("Caption")}</label>
                            <textarea id="cf-studio-editor-caption" className="cf-textarea cf-textarea-sm" rows={3} value={currentContent?.caption || ""} onChange={(event) => setCurrentTextField("caption", event.target.value)} />
                          </div>
                          <div className="cf-field">
                            <label className="cf-field-label" htmlFor="cf-studio-editor-slides">{translator.tr("Carousel")}</label>
                            <textarea id="cf-studio-editor-slides" className="cf-textarea" rows={6} placeholder="Headline | Body" value={carouselSlidesText} onChange={(event) => setCurrentSlidesFromText(event.target.value)} />
                          </div>
                        </>
                      ) : null}

                      {currentFormat === "story_sequence" ? (
                        <div className="cf-field">
                          <label className="cf-field-label" htmlFor="cf-studio-editor-frames">{translator.tr("Story sequence")}</label>
                          <textarea id="cf-studio-editor-frames" className="cf-textarea" rows={6} value={storyFramesText} onChange={(event) => setCurrentFramesFromText(event.target.value)} />
                        </div>
                      ) : null}

                      {currentFormat === "reel_script" ? (
                        <div className="cf-field">
                          <label className="cf-field-label" htmlFor="cf-studio-editor-points">{translator.tr("Proof points and key points")}</label>
                          <textarea id="cf-studio-editor-points" className="cf-textarea" rows={6} value={reelPointsText} onChange={(event) => setCurrentPointsFromText(event.target.value)} />
                        </div>
                      ) : null}

                      {(currentFormat === "post" || currentFormat === "reel_script") ? (
                        <div className="cf-field">
                          <label className="cf-field-label" htmlFor="cf-studio-editor-cta">{translator.tr("Closing CTA")}</label>
                          <textarea id="cf-studio-editor-cta" className="cf-textarea cf-textarea-sm" rows={2} value={currentContent?.cta || ""} onChange={(event) => setCurrentTextField("cta", event.target.value)} />
                        </div>
                      ) : null}

                      <div className="cf-studio-brief-grid">
                        <div className="cf-field">
                          <label className="cf-field-label" htmlFor="cf-studio-editor-hashtags">{translator.tr("Hashtags")}</label>
                          <input id="cf-studio-editor-hashtags" className="cf-input" type="text" value={editorHashtags} onChange={(event) => setCurrentHashtags(event.target.value)} />
                        </div>
                        {(currentFormat === "post" || currentFormat === "carousel") ? (
                          <div className="cf-field">
                            <label className="cf-field-label" htmlFor="cf-studio-editor-image">{translator.tr("Image path")}</label>
                            <input id="cf-studio-editor-image" className="cf-input" type="text" value={currentContent?.image_path || ""} onChange={(event) => setCurrentTextField("image_path", event.target.value)} />
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : (
                    <EmptyState title={translator.tr("No draft selected")} copy={translator.tr("Choose an item from the library or create a new draft.")} />
                  )}
                </div>
              </article>
            </section>

            <aside className="cf-studio-side-rail">
              <article className="cf-card cf-panel cf-studio-publish-card">
                <div className="cf-studio-panel-head cf-studio-panel-head-simple">
                  <div className="cf-studio-panel-copy">
                    <div className="cf-studio-mini-kicker">{translator.tr("Publish route")}</div>
                    <h2 className="cf-studio-panel-title">{translator.tr("Choose the next action")}</h2>
                    <p className="cf-inline-note">{translator.tr("Choose what the agent should save, review, schedule, or publish.")}</p>
                  </div>
                </div>
                <div id="cf-studio-preview-meta" className="cf-studio-route-card" aria-live="polite">
                  <div className="cf-route-kicker">{translator.tr("Publish route")}</div>
                  <div className="cf-route-title">{translator.tr("{destination} via {platform}", { destination: page?.page_name || translator.tr("No active destination"), platform: platformLabel(brief.platform, translator) })}</div>
                  <div className="cf-studio-route-grid">
                    <div>
                      <span className="cf-label">{translator.tr("Schedule")}</span>
                      <strong>{brief.schedule || translator.tr("Not scheduled")}</strong>
                    </div>
                    <div>
                      <span className="cf-label">{translator.tr("State")}</span>
                      <strong>{current?.id ? statusLabel(current.status || "draft_only", translator) : translator.tr("Unsaved preview")}</strong>
                    </div>
                  </div>
                </div>
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-studio-schedule">{translator.tr("Scheduled time")}</label>
                  <input id="cf-studio-schedule" className="cf-input" type="datetime-local" value={brief.schedule} onChange={(event: ChangeEvent<HTMLInputElement>) => setBriefField("schedule", event.target.value)} />
                  <div className="cf-tz-hint" id="cf-studio-tz-hint">{Intl.DateTimeFormat().resolvedOptions().timeZone}</div>
                </div>
                <div className="cf-action-stack cf-studio-publish-actions">
                  <button type="button" className="cf-btn" id="cf-studio-primary-action" onClick={() => void handlePrimaryAction()} disabled={busy}>{busy ? translator.tr("Working...") : primaryLabel}</button>
                  <button type="button" className="cf-btn-ghost" id="cf-studio-secondary-action" onClick={() => void handleSecondaryAction()} disabled={busy || secondaryDisabled}>{busy ? translator.tr("Working...") : secondaryLabel}</button>
                  <button type="button" className="cf-btn-ghost cf-btn-danger-soft" id="cf-studio-tertiary-action" onClick={() => void handleTertiaryAction()} disabled={busy}>{busy ? translator.tr("Working...") : tertiaryLabel}</button>
                </div>
              </article>

              <article className="cf-card cf-panel cf-studio-insights-card">
                <div className="cf-studio-panel-head cf-studio-panel-head-simple">
                  <div className="cf-studio-panel-copy">
                    <div className="cf-studio-mini-kicker">{translator.tr("Agent plan")}</div>
                    <h2 className="cf-studio-panel-title">{translator.tr("Quick creative cues")}</h2>
                    <p className="cf-inline-note">{translator.tr("What the agent understands from your current parameters.")}</p>
                  </div>
                </div>
                <div id="cf-studio-brief-summary" className="cf-studio-insights-list" aria-live="polite">
                  {insightCards.map((card) => (
                    <article key={card.title} className="cf-studio-summary-card">
                      <div className="cf-summary-copy">
                        <div className="cf-label">{card.title}</div>
                        <div className="cf-summary-value">{card.value}</div>
                      </div>
                      <div className="cf-inline-note">{card.copy}</div>
                    </article>
                  ))}
                </div>
              </article>
            </aside>
          </div>
        </div>
      </section>

      {error && !loading && !payload ? (
        <article className="cf-card cf-panel">
          <ErrorState title={translator.tr("Something failed to load")} copy={translator.maybeTr(error)} />
        </article>
      ) : null}
    </section>
  );
}
