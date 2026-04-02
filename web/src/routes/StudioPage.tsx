import { CSSProperties, ChangeEvent, Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { apiCall, apiFetch, BootstrapResponse } from "../lib/api";
import { BootPayload } from "../lib/boot";
import { Translator } from "../lib/i18n";
import { resolveStudioLayoutMode, StudioLayoutMode } from "../lib/studioLayout";
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
import { NeonButton, ShimmerSkeleton } from "../ui/primitives";

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
  template_defaults?: Record<string, unknown>;
};

type StudioCollections = Record<StudioTab, StudioItem[]>;
type StudioAdvancedPanel = "brand" | "layout" | "media";
type StudioAssetUploadKind = "main-image" | "background";

type StudioAssetUploadResponse = {
  success: boolean;
  kind: StudioAssetUploadKind;
  content_id?: string;
  image_path?: string;
  image_url?: string;
  public_url?: string;
  backgroundImagePath?: string;
};

type StudioTemplateDesign = {
  brandName: string;
  socialHandle: string;
  backgroundImagePath: string;
  backgroundDensity: number;
  backgroundZoom: number;
  backgroundOffsetX: number;
  backgroundOffsetY: number;
  mediaWidth: number;
  mediaHeight: number;
  mediaZoom: number;
  mediaClarity: number;
  mediaOffsetX: number;
  mediaOffsetY: number;
  mediaFit: "contain" | "cover";
  titleScale: number;
  titleOffsetY: number;
  titleWidth: number;
  titleFontFamily: "display" | "body" | "mono";
  titleColor: string;
  showSocialStrip: boolean;
  showBrandBadge: boolean;
  mediaFullBleed: boolean;
};

const DEFAULT_TEMPLATE: StudioTemplateDesign = {
  brandName: "",
  socialHandle: "",
  backgroundImagePath: "",
  backgroundDensity: 48,
  backgroundZoom: 100,
  backgroundOffsetX: 0,
  backgroundOffsetY: 0,
  mediaWidth: 88,
  mediaHeight: 178,
  mediaZoom: 100,
  mediaClarity: 100,
  mediaOffsetX: 0,
  mediaOffsetY: 0,
  mediaFit: "cover",
  titleScale: 100,
  titleOffsetY: 0,
  titleWidth: 94,
  titleFontFamily: "display",
  titleColor: "#fff8ef",
  showSocialStrip: true,
  showBrandBadge: false,
  mediaFullBleed: false,
};

function normalizeTemplateDefaults(raw: unknown): Partial<StudioTemplateDesign> {
  const data = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
  const next: Partial<StudioTemplateDesign> = {};

  if ("brandName" in data) next.brandName = String(data.brandName || "").trim();
  if ("socialHandle" in data) next.socialHandle = String(data.socialHandle || "").trim();
  if ("backgroundImagePath" in data) next.backgroundImagePath = String(data.backgroundImagePath || "").trim();

  const backgroundDensity = Number(data.backgroundDensity);
  if (Number.isFinite(backgroundDensity)) next.backgroundDensity = Math.min(100, Math.max(0, backgroundDensity));

  const backgroundZoom = Number(data.backgroundZoom);
  if (Number.isFinite(backgroundZoom)) next.backgroundZoom = Math.min(180, Math.max(40, backgroundZoom));

  const backgroundOffsetX = Number(data.backgroundOffsetX);
  if (Number.isFinite(backgroundOffsetX)) next.backgroundOffsetX = Math.min(40, Math.max(-40, backgroundOffsetX));

  const backgroundOffsetY = Number(data.backgroundOffsetY);
  if (Number.isFinite(backgroundOffsetY)) next.backgroundOffsetY = Math.min(40, Math.max(-40, backgroundOffsetY));

  const mediaWidth = Number(data.mediaWidth);
  if (Number.isFinite(mediaWidth)) next.mediaWidth = Math.min(100, Math.max(30, mediaWidth));

  const mediaHeight = Number(data.mediaHeight);
  if (Number.isFinite(mediaHeight)) next.mediaHeight = Math.min(260, Math.max(110, mediaHeight));

  const mediaZoom = Number(data.mediaZoom);
  if (Number.isFinite(mediaZoom)) next.mediaZoom = Math.min(220, Math.max(40, mediaZoom));

  const mediaClarity = Number(data.mediaClarity);
  if (Number.isFinite(mediaClarity)) next.mediaClarity = Math.min(140, Math.max(80, mediaClarity));

  const mediaOffsetX = Number(data.mediaOffsetX);
  if (Number.isFinite(mediaOffsetX)) next.mediaOffsetX = Math.min(60, Math.max(-60, mediaOffsetX));

  const mediaOffsetY = Number(data.mediaOffsetY);
  if (Number.isFinite(mediaOffsetY)) next.mediaOffsetY = Math.min(60, Math.max(-60, mediaOffsetY));

  const titleScale = Number(data.titleScale);
  if (Number.isFinite(titleScale)) next.titleScale = Math.min(140, Math.max(80, titleScale));

  const titleOffsetY = Number(data.titleOffsetY);
  if (Number.isFinite(titleOffsetY)) next.titleOffsetY = Math.min(24, Math.max(-24, titleOffsetY));

  const titleWidth = Number(data.titleWidth);
  if (Number.isFinite(titleWidth)) next.titleWidth = Math.min(100, Math.max(68, titleWidth));

  if (data.titleFontFamily === "display" || data.titleFontFamily === "body" || data.titleFontFamily === "mono") {
    next.titleFontFamily = data.titleFontFamily;
  }

  const titleColor = String(data.titleColor || "").trim();
  if (/^#[0-9a-f]{6}$/i.test(titleColor)) {
    next.titleColor = titleColor;
  }

  if (data.mediaFit === "contain" || data.mediaFit === "cover") {
    next.mediaFit = data.mediaFit;
  }
  if (typeof data.showSocialStrip === "boolean") next.showSocialStrip = data.showSocialStrip;
  if (typeof data.showBrandBadge === "boolean") next.showBrandBadge = data.showBrandBadge;
  if (typeof data.mediaFullBleed === "boolean") next.mediaFullBleed = data.mediaFullBleed;

  return next;
}

function buildTemplateSettingsPayload(template: StudioTemplateDesign) {
  return {
    brandName: template.brandName,
    socialHandle: template.socialHandle,
    backgroundImagePath: template.backgroundImagePath,
    backgroundDensity: template.backgroundDensity,
    backgroundZoom: template.backgroundZoom,
    backgroundOffsetX: template.backgroundOffsetX,
    backgroundOffsetY: template.backgroundOffsetY,
    mediaWidth: template.mediaWidth,
    mediaHeight: template.mediaHeight,
    mediaZoom: template.mediaZoom,
    mediaClarity: template.mediaClarity,
    mediaOffsetX: template.mediaOffsetX,
    mediaOffsetY: template.mediaOffsetY,
    mediaFit: template.mediaFit,
    titleScale: template.titleScale,
    titleOffsetY: template.titleOffsetY,
    titleWidth: template.titleWidth,
    titleFontFamily: template.titleFontFamily,
    titleColor: template.titleColor,
    showSocialStrip: template.showSocialStrip,
    showBrandBadge: template.showBrandBadge,
    mediaFullBleed: template.mediaFullBleed,
  };
}

function assetLabel(value: string): string {
  const trimmed = String(value || "").trim();
  if (!trimmed) return "";
  const [withoutQuery] = trimmed.split("?");
  const parts = withoutQuery.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || trimmed;
}

function appendCacheBust(url: string): string {
  const trimmed = String(url || "").trim();
  if (!trimmed) return "";
  const glue = trimmed.includes("?") ? "&" : "?";
  return `${trimmed}${glue}v=${Date.now()}`;
}

const _FS_PATH_RE = /^\/(home|var|tmp|root|usr|opt|srv|runner)\//;

function resolveStudioImagePreviewUrl(imagePath: string, contentId?: string | null, optimisticUrl?: string): string {
  const optimistic = String(optimisticUrl || "").trim();
  if (optimistic) return optimistic;
  const trimmed = String(imagePath || "").trim();
  if (!trimmed) return "";
  const isWebUrl = /^(https?:)?\/\//.test(trimmed) || (trimmed.startsWith("/") && !_FS_PATH_RE.test(trimmed));
  if (isWebUrl) {
    return appendCacheBust(trimmed);
  }
  return contentId ? appendCacheBust(`/api/content/${contentId}/image`) : "";
}

function resolveTemplateTitleFont(fontFamily: StudioTemplateDesign["titleFontFamily"]): string {
  if (fontFamily === "body") return "var(--font-body)";
  if (fontFamily === "mono") return "var(--font-mono)";
  return "var(--font-display)";
}

function buildTemplateAutomationNote(template: StudioTemplateDesign, translator: Translator): string {
  const notes = [
    translator.tr("Keep the publish surface visually calm and creator-ready."),
    template.backgroundImagePath.trim()
      ? translator.tr("Background image framing: {zoom}% zoom with focus {x}% / {y}%.", {
        zoom: String(template.backgroundZoom),
        x: String(template.backgroundOffsetX),
        y: String(template.backgroundOffsetY),
      })
      : translator.tr("Use a clean background layer behind the main publication image."),
    translator.tr("Artwork scale target: {size}% width and {zoom}% zoom.", {
      size: String(template.mediaWidth),
      zoom: String(template.mediaZoom),
    }),
    translator.tr("Artwork crop: {fit} with focus {x}% / {y}%.", {
      fit: template.mediaFit,
      x: String(template.mediaOffsetX),
      y: String(template.mediaOffsetY),
    }),
    translator.tr("Title emphasis: {scale}% scale with {width}% width and {offset}% vertical offset.", {
      scale: String(template.titleScale),
      width: String(template.titleWidth),
      offset: String(template.titleOffsetY),
    }),
  ];
  if (template.showSocialStrip) {
    notes.push(translator.tr("Reserve space for a social handle strip."));
  }
  return notes.join(" ");
}

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

function previewSeed(input: string): number {
  return Array.from(input).reduce((total, char) => total + char.charCodeAt(0), 0);
}

function compactMetric(value: number): string {
  if (value >= 10000) {
    return `${Math.round(value / 1000)}K`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1).replace(".0", "")}K`;
  }
  return String(value);
}

function SocialIcon({ kind }: { kind: "heart" | "comment" | "send" | "save" | "more" | "play" | "thumbup" | "fbshare" }) {
  if (kind === "heart") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 20.5 4.8 13.7A4.8 4.8 0 0 1 11.6 7L12 7.4l.4-.4a4.8 4.8 0 0 1 6.8 6.7Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (kind === "thumbup") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 22V11M2 13v7a2 2 0 0 0 2 2h11.4a2 2 0 0 0 1.98-1.72l1.06-8A2 2 0 0 0 16.46 9H13V5a2 2 0 0 0-2-2 1 1 0 0 0-1 1v.5L7.5 10.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (kind === "comment") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 6.5h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H10l-5 3v-3H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (kind === "send") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m20 4-8.8 16-1.9-6.1L3 12.1 20 4Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (kind === "fbshare") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 12v5a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-5M12 3v12M8 7l4-4 4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (kind === "save") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 4.5h10a1.5 1.5 0 0 1 1.5 1.5v13l-6.5-3.7L5.5 19V6A1.5 1.5 0 0 1 7 4.5Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (kind === "play") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 7.2v9.6l7.8-4.8L9 7.2Z" fill="currentColor" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="6" cy="12" r="1.6" fill="currentColor" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" />
      <circle cx="18" cy="12" r="1.6" fill="currentColor" />
    </svg>
  );
}

function PhoneStatusBar({ dark }: { dark?: boolean }) {
  const now = new Date();
  const h = now.getHours();
  const m = String(now.getMinutes()).padStart(2, "0");
  const time = `${h}:${m}`;
  return (
    <div className={`cf-phone-status-bar${dark ? " is-dark" : ""}`} aria-hidden="true">
      <span className="cf-phone-status-time">{time}</span>
      <div className="cf-phone-status-icons">
        <svg viewBox="0 0 18 12" className="cf-phone-status-signal" fill="currentColor">
          <rect x="0" y="8" width="3" height="4" rx="0.5" />
          <rect x="4.5" y="5" width="3" height="7" rx="0.5" />
          <rect x="9" y="2" width="3" height="10" rx="0.5" />
          <rect x="13.5" y="0" width="3" height="12" rx="0.5" opacity="0.3" />
        </svg>
        <svg viewBox="0 0 18 14" className="cf-phone-status-wifi" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          <path d="M1 5C4.8 1.2 13.2 1.2 17 5" />
          <path d="M3.5 7.5C6.2 4.8 11.8 4.8 14.5 7.5" />
          <path d="M6.5 10C8 8.5 10 8.5 11.5 10" />
          <circle cx="9" cy="13" r="1" fill="currentColor" stroke="none" />
        </svg>
        <svg viewBox="0 0 26 13" className="cf-phone-status-battery" fill="currentColor">
          <rect x="0.75" y="0.75" width="21.5" height="11.5" rx="2.75" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <rect x="2.5" y="2.5" width="16" height="8" rx="1.5" />
          <path d="M23.5 4.5v4a2 2 0 0 0 0-4Z" />
        </svg>
      </div>
    </div>
  );
}

function TemplateCanvas({
  surface,
  pageName,
  translator,
  template,
  fallbackMediaUrl,
  titleText,
  supportText,
}: {
  surface: string;
  pageName: string;
  translator: Translator;
  template: StudioTemplateDesign;
  fallbackMediaUrl: string;
  titleText: string;
  supportText: string;
}) {
  const socialHandle = template.socialHandle.trim() || pageName.replace(/\s+/g, "").toLowerCase();
  const handleLabel = `@${socialHandle.replace(/^@+/, "")}`;
  const brandLabel = template.brandName.trim() || pageName;
  const mediaUrl = fallbackMediaUrl || "";
  const backgroundImagePath = template.backgroundImagePath.trim();
  const backgroundTitle = titleText.trim();
  const backgroundSupport = supportText.trim();
  const canvasClassName = `cf-template-canvas ${surface === "instagram" ? "is-instagram" : "is-facebook"}${template.mediaFullBleed ? " is-fullbleed" : ""}`;
  const style = {
    "--cf-template-background-zoom": String(template.backgroundZoom / 100),
    "--cf-template-background-offset-x": `${template.backgroundOffsetX}%`,
    "--cf-template-background-offset-y": `${template.backgroundOffsetY}%`,
    "--cf-template-media-width": `${template.mediaWidth}%`,
    "--cf-template-media-height": `${template.mediaHeight}px`,
    "--cf-template-bg-density": `${template.backgroundDensity / 100}`,
    "--cf-template-media-zoom": `${template.mediaZoom / 100}`,
    "--cf-template-media-clarity": `${template.mediaClarity / 100}`,
    "--cf-template-media-offset-x": `${template.mediaOffsetX}%`,
    "--cf-template-media-offset-y": `${template.mediaOffsetY}%`,
    "--cf-template-media-fit": template.mediaFit,
    "--cf-template-title-scale": String(template.titleScale / 100),
    "--cf-template-title-offset-y": `${template.titleOffsetY}px`,
    "--cf-template-title-width": `${template.titleWidth}%`,
    "--cf-template-title-color": template.titleColor,
    "--cf-template-title-font": resolveTemplateTitleFont(template.titleFontFamily),
  } as CSSProperties;

  return (
    <div className={canvasClassName} style={style}>
      <div className="cf-template-bg">
        {backgroundImagePath ? (
          <div
            className="cf-template-bg-media"
            style={{ backgroundImage: `url("${backgroundImagePath.replace(/"/g, '\\"')}")` }}
            aria-hidden="true"
          />
        ) : null}
      </div>
      <div className="cf-template-overlay" />
      <div className="cf-template-stage">
        {template.showSocialStrip ? (
          <div className="cf-template-brand-strip">
            <div className="cf-template-social-group">
              <div className="cf-template-social-icons" aria-hidden="true">
                <span>f</span>
                <span>ig</span>
                <span>x</span>
              </div>
              <span className="cf-template-social-handle">{handleLabel}</span>
            </div>
            {template.showBrandBadge ? <span className="cf-template-brand-chip">{brandLabel}</span> : null}
          </div>
        ) : null}
        <div className="cf-template-media-zone">
          <div className={`cf-template-media-viewport ${mediaUrl ? "" : "is-empty"}`}>
            {mediaUrl ? (
              <img src={mediaUrl} alt={translator.tr("Template media preview")} />
            ) : (
              <div className="cf-template-media-placeholder">
                <span>{translator.tr("Drop a publication image")}</span>
              </div>
            )}
          </div>
        </div>
        <div className="cf-template-title-zone">
          <div className="cf-template-title-block">
            <h3>{backgroundTitle || translator.tr("Your headline here")}</h3>
            {backgroundSupport ? <p>{backgroundSupport}</p> : null}
          </div>
        </div>
      </div>
    </div>
  );
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
      cta: "",
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

function PreviewBody({
  current,
  surface,
  translator,
  pageName,
  briefPlatformLabel,
  template,
  mediaUrl,
}: {
  current: StudioItem;
  surface: string;
  translator: Translator;
  pageName: string;
  briefPlatformLabel: string;
  template: StudioTemplateDesign;
  mediaUrl: string;
}) {
  const content = current.content_normalized;
  const format = String(content.format || current.post_type || "post").toLowerCase();
  const surfaceLabel = translator.tr(surface === "instagram" ? "Instagram" : "Facebook");
  const isInstagram = surface === "instagram";
  const primaryText = String(content.hook || "").trim() || translator.tr(format === "reel_script" ? "Reel hook" : "Post hook");
  const secondaryText = String(content.body || content.caption || content.cta || "").trim();
  const captionText = [primaryText, secondaryText].filter(Boolean).join("\n\n");
  const hashtagsText = content.hashtags.join(" ");
  const seed = previewSeed(`${pageName}:${surface}:${format}:${captionText}:${hashtagsText}`);
  const likes = 64 + (seed % 540);
  const comments = 6 + (seed % 44);
  const shares = 2 + (seed % 18);
  const saves = 9 + (seed % 37);
  const views = 1200 + (seed % 8400);
  const storyFrames = content.frames.length ? content.frames : [{ text: primaryText, visual_suggestion: briefPlatformLabel }];
  const carouselSlides = content.slides.length
    ? content.slides
    : [{ headline: primaryText, body: secondaryText || translator.tr("Slide body"), visual_suggestion: translator.tr("Visual direction") }];
  const instagramHandle = (template.socialHandle.trim() || pageName.replace(/\s+/g, "").toLowerCase()).replace(/^@+/, "");
  const facebookMeta = `${translator.tr("Just now")} • ${translator.tr("Public")}`;
  const instagramMeta = translator.tr("Original audio");
  const facebookPreviewCopy = secondaryText || (!mediaUrl && !template.backgroundImagePath ? primaryText : "");
  const topHeader = isInstagram ? (
    <div className="cf-social-post-header is-instagram">
      <div className="cf-social-identity">
        <div className="cf-ig-avatar-ring">
          <div className="cf-surface-avatar">{initials(pageName)}</div>
        </div>
        <div className="cf-social-meta is-instagram">
          <strong>{instagramHandle}</strong>
          <span className="cf-ig-follow-link">{translator.tr("Follow")}</span>
        </div>
      </div>
      <div className="cf-social-header-actions">
        <button type="button" className="cf-social-more" aria-label={translator.tr("More")}>
          <SocialIcon kind="more" />
        </button>
      </div>
    </div>
  ) : (
    <div className="cf-social-post-header is-facebook">
      <div className="cf-social-identity">
        <div className="cf-surface-avatar">{initials(pageName)}</div>
        <div className="cf-social-meta is-facebook">
          <strong>{pageName}</strong>
          <span>{facebookMeta}</span>
        </div>
      </div>
      <div className="cf-social-header-actions">
        <button type="button" className="cf-fb-follow-btn" aria-label={translator.tr("Follow")}>{translator.tr("Follow")}</button>
        <button type="button" className="cf-social-more" aria-label={translator.tr("More")}>
          <SocialIcon kind="more" />
        </button>
      </div>
    </div>
  );

  const instagramActions = (
    <div className="cf-social-icon-row" aria-hidden="true">
      <div className="cf-social-icon-cluster">
        <span className="cf-social-icon-btn"><SocialIcon kind="heart" /></span>
        <span className="cf-social-icon-btn"><SocialIcon kind="comment" /></span>
        <span className="cf-social-icon-btn"><SocialIcon kind="send" /></span>
      </div>
      <span className="cf-social-icon-btn"><SocialIcon kind="save" /></span>
    </div>
  );

  const facebookReactionBadges = (
    <div className="cf-social-reaction-badges" aria-hidden="true">
      <span className="is-like">👍</span>
      <span className="is-love">❤</span>
    </div>
  );

  const facebookActions = (
    <div className="cf-social-action-row" aria-hidden="true">
      <button type="button" className="cf-social-action-text">
        <SocialIcon kind="thumbup" />{translator.tr("Like")}
      </button>
      <button type="button" className="cf-social-action-text">
        <SocialIcon kind="comment" />{translator.tr("Comment")}
      </button>
      <button type="button" className="cf-social-action-text">
        <SocialIcon kind="fbshare" />{translator.tr("Share")}
      </button>
    </div>
  );

  if (format === "carousel") {
    return (
      <article className={`cf-social-surface cf-social-feed is-${surface} is-carousel`}>
        {topHeader}
        <div className={`cf-social-media cf-social-carousel-shell ${isInstagram ? "is-portrait" : "is-landscape"}`}>
          <div className="cf-social-carousel-stack">
            {carouselSlides.slice(0, 3).map((slide, index) => (
              <article key={`slide-${index}`} className={`cf-social-carousel-card is-card-${index + 1}`}>
                <div className="cf-social-carousel-count">{index + 1}/{carouselSlides.length}</div>
                <div className="cf-social-carousel-title">{slide.headline || translator.tr("Slide headline")}</div>
                <div className="cf-social-carousel-copy">{renderLines(String(slide.body || translator.tr("Slide body")))}</div>
              </article>
            ))}
          </div>
          <div className="cf-social-carousel-dots" aria-hidden="true">
            {carouselSlides.slice(0, Math.min(carouselSlides.length, 5)).map((_, index) => (
              <span key={`dot-${index}`} className={`cf-social-carousel-dot ${index === 0 ? "is-active" : ""}`} />
            ))}
          </div>
        </div>
        {isInstagram ? instagramActions : null}
      <div className="cf-social-engagement">
        <strong>{compactMetric(isInstagram ? likes : likes + shares)} {translator.tr(isInstagram ? "likes" : "reactions")}</strong>
        {!isInstagram ? <span>{compactMetric(comments)} {translator.tr("comments")} - {compactMetric(shares)} {translator.tr("shares")}</span> : null}
        </div>
        <div className="cf-social-copy">
          <strong>{pageName}</strong>
          <span>{renderLines(String(content.caption || translator.tr("No caption yet.")))}</span>
        </div>
        {hashtagsText ? <div className="cf-preview-footer">{hashtagsText}</div> : null}
        {isInstagram ? <div className="cf-social-comment-box">{translator.tr("Add a comment...")}</div> : facebookActions}
      </article>
    );
  }

  if (format === "story_sequence") {
    return (
      <article className={`cf-social-surface cf-social-story-shell is-${surface}`}>
        <div className="cf-social-story-progress" aria-hidden="true">
          {storyFrames.slice(0, Math.min(storyFrames.length, 5)).map((_, index) => (
            <span key={`story-progress-${index}`} className={`cf-social-story-progress-bar ${index === 0 ? "is-active" : ""}`} />
          ))}
        </div>
        <div className="cf-social-story-top">
          <div className="cf-social-identity">
            <div className="cf-surface-avatar">{initials(pageName)}</div>
            <div className="cf-social-meta">
              <strong>{pageName}</strong>
              <span>{surfaceLabel} Stories - {translator.tr("Just now")}</span>
            </div>
          </div>
          <button type="button" className="cf-social-more" aria-label={translator.tr("More")}>
            <SocialIcon kind="more" />
          </button>
        </div>
        <div className="cf-social-story-frame">
          <div className="cf-social-story-card">
            <span className="cf-social-story-chip">{translator.tr("Story {index}", { index: 1 })}</span>
            <div className="cf-social-story-copy">{renderLines(String(storyFrames[0].text || translator.tr("Frame text")))}</div>
            <div className="cf-social-story-note">{storyFrames[0].visual_suggestion || translator.tr("Add visual direction for the story sequence.")}</div>
          </div>
        </div>
        <div className="cf-social-story-reply">{translator.tr("Send message")}</div>
      </article>
    );
  }

  if (format === "reel_script") {
    return (
      <article className={`cf-social-surface cf-social-reel-shell is-${surface}`}>
        <div className="cf-social-reel-stage">
          <div className="cf-social-reel-top">
            <span className="cf-platform-chip">{translator.tr(isInstagram ? "Reels" : "Video")}</span>
            <span className="cf-social-reel-audio">{pageName}</span>
          </div>
          <div className="cf-social-reel-center">
            <div className="cf-social-reel-play">
              <SocialIcon kind="play" />
            </div>
            <div className="cf-social-reel-hook">{primaryText}</div>
            <div className="cf-social-reel-points">
              {(content.points.length ? content.points : [translator.tr("Add talking points for the reel script.")]).slice(0, 4).map((point, index) => (
                <div key={`reel-point-${index}`} className="cf-social-reel-point">
                  <span>{index + 1}</span>
                  <p>{point}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="cf-social-reel-bottom">
            <strong>{pageName}</strong>
            <span>{content.cta || translator.tr("Add a closing CTA to tighten the script.")}</span>
            {hashtagsText ? <div className="cf-preview-footer">{hashtagsText}</div> : null}
          </div>
        </div>
        <div className="cf-social-reel-actions" aria-hidden="true">
          <span className="cf-social-reel-action"><SocialIcon kind="heart" /><small>{compactMetric(likes)}</small></span>
          <span className="cf-social-reel-action"><SocialIcon kind="comment" /><small>{compactMetric(comments)}</small></span>
          <span className="cf-social-reel-action"><SocialIcon kind="send" /><small>{compactMetric(shares)}</small></span>
          <span className="cf-social-reel-action"><SocialIcon kind="more" /></span>
        </div>
      </article>
    );
  }

  const fbCopyFull = [facebookPreviewCopy, hashtagsText].filter(Boolean).join(" ");
  const fbCopyTrunc = fbCopyFull.length > 120;
  const fbCopyDisplay = fbCopyTrunc ? fbCopyFull.slice(0, 120).trimEnd() + "…" : fbCopyFull;

  return (
    <article className={`cf-social-surface cf-social-feed is-${surface} is-post`}>
      {topHeader}
      {!isInstagram ? (
        <div className="cf-social-copy is-facebook-copy">
          {fbCopyDisplay ? <span>{renderLines(fbCopyDisplay)}</span> : null}
          {fbCopyTrunc ? <span className="cf-social-see-more">{translator.tr("See more")}</span> : null}
        </div>
      ) : null}
      <figure className={`cf-social-media ${isInstagram ? "is-portrait" : "is-facebook"} ${mediaUrl ? "" : "is-placeholder"}`}>
        <TemplateCanvas
          surface={surface}
          pageName={pageName}
          translator={translator}
          template={template}
          fallbackMediaUrl={mediaUrl}
          titleText={primaryText}
          supportText={secondaryText}
        />
      </figure>
      {isInstagram ? instagramActions : null}
      {isInstagram ? (
        <div className="cf-social-engagement is-instagram-summary">
          <strong>{compactMetric(likes)} {translator.tr("likes")}</strong>
        </div>
      ) : (
        <div className="cf-social-engagement is-facebook-summary">
          <div className="cf-social-engagement-primary">
            {facebookReactionBadges}
            <strong>{compactMetric(likes + shares)} {translator.tr("reactions")}</strong>
          </div>
          <span>{compactMetric(comments)} {translator.tr("comments")} · {compactMetric(shares)} {translator.tr("shares")}</span>
        </div>
      )}
      {isInstagram ? (
        <div className="cf-social-copy is-instagram-copy">
          <strong>{instagramHandle}</strong>
          <span>{renderLines(captionText.length > 100 ? captionText.slice(0, 100).trimEnd() + "… " : captionText)}</span>
          {captionText.length > 100 ? <span className="cf-social-see-more">{translator.tr("more")}</span> : null}
          {hashtagsText ? <div className="cf-social-hashtag-line">{hashtagsText}</div> : null}
        </div>
      ) : null}
      {isInstagram ? (
        <>
          <div className="cf-social-inline-note">{translator.tr("View all {count} comments", { count: compactMetric(comments) })}</div>
          <div className="cf-social-comment-box">{translator.tr("Add a comment...")}</div>
        </>
      ) : (
        facebookActions
      )}
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
  const [templatePreviewOpen, setTemplatePreviewOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [advancedPanels, setAdvancedPanels] = useState<Record<StudioAdvancedPanel, boolean>>({
    brand: true,
    layout: false,
    media: false,
  });
  const [composerSection, setComposerSection] = useState<"idea" | "template" | "copy">("idea");
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
  const [template, setTemplate] = useState<StudioTemplateDesign>(DEFAULT_TEMPLATE);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [studioLayout, setStudioLayout] = useState<StudioLayoutMode>("stacked");
  const briefRef = useRef(brief);
  const currentIdRef = useRef<string | null>(current?.id ?? null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const mainImageInputRef = useRef<HTMLInputElement | null>(null);
  const backgroundImageInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadingMainImage, setUploadingMainImage] = useState(false);
  const [uploadingBackgroundImage, setUploadingBackgroundImage] = useState(false);
  const [mainImagePreviewOverride, setMainImagePreviewOverride] = useState("");

  const desktopCanvas = studioLayout !== "stacked";
  const centeredCanvasDesktop = studioLayout === "centered";

  useEffect(() => {
    briefRef.current = brief;
  }, [brief]);

  useEffect(() => {
    currentIdRef.current = current?.id ?? null;
  }, [current?.id]);

  useEffect(() => {
    setMainImagePreviewOverride("");
  }, [current?.id]);

  useEffect(() => {
    if (!templatePreviewOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setTemplatePreviewOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [templatePreviewOpen]);

  const toggleAdvancedPanel = useCallback((panel: StudioAdvancedPanel) => {
    setAdvancedPanels((currentPanels) => ({
      ...currentPanels,
      [panel]: !currentPanels[panel],
    }));
  }, []);

  useLayoutEffect(() => {
    const stageNode = stageRef.current;
    if (!stageNode) {
      return;
    }

    const syncLayoutMode = (nextWidth: number) => {
      const nextMode = resolveStudioLayoutMode(nextWidth);
      setStudioLayout((currentMode) => (currentMode === nextMode ? currentMode : nextMode));
    };

    const readStageWidth = () => {
      const measuredWidth = stageNode.clientWidth || stageNode.getBoundingClientRect().width || 0;
      syncLayoutMode(measuredWidth);
    };

    readStageWidth();

    if (typeof ResizeObserver === "function") {
      const observer = new ResizeObserver((entries) => {
        const observedEntry = entries.find((entry) => entry.target === stageNode) || entries[0];
        syncLayoutMode(observedEntry?.contentRect.width || stageNode.clientWidth || 0);
      });

      observer.observe(stageNode);
      return () => observer.disconnect();
    }

    const handleResize = () => readStageWidth();
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
    const templateDefaults = normalizeTemplateDefaults(profileData.template_defaults);
    if (Object.keys(templateDefaults).length) {
      setTemplate((currentTemplate) => ({
        ...currentTemplate,
        ...templateDefaults,
      }));
    }
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
        platform: platformValueFromRaw(local.platforms || fallbackPlatforms),
        schedule: local.scheduled_time ? localDateTime(local.scheduled_time) : nextSlot(),
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
        platform: platformValueFromRaw(normalized.platforms || fallbackPlatforms),
        schedule: normalized.scheduled_time ? localDateTime(normalized.scheduled_time) : nextSlot(),
      }));
    } catch (_error) {
      const fallbackItem = normalizeStudioItem({
        id: target,
        content_id: target,
        post_type: "post",
        generated_text: meta?.text || "",
        status: meta?.published_at ? "published" : "scheduled",
        scheduled_time: meta?.scheduled_time,
        published_at: meta?.published_at,
        platforms: meta?.platforms || fallbackPlatforms,
      }, fallbackPlatforms);
      setCurrent(fallbackItem);
      setBrief((currentBrief) => ({
        ...currentBrief,
        platform: platformValueFromRaw(fallbackItem.platforms || fallbackPlatforms),
        schedule: fallbackItem.scheduled_time ? localDateTime(fallbackItem.scheduled_time) : nextSlot(),
      }));
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

  const setTemplateField = useCallback(<K extends keyof StudioTemplateDesign>(field: K, value: StudioTemplateDesign[K]) => {
    setTemplate((currentTemplate) => ({ ...currentTemplate, [field]: value }));
  }, []);

  const focusEditorField = useCallback((ref: { current: HTMLInputElement | null }) => {
    ref.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    if (ref.current?.type === "file") {
      ref.current.click();
      return;
    }
    ref.current?.focus();
  }, []);

  const uploadStudioAsset = useCallback(async (formData: FormData): Promise<StudioAssetUploadResponse> => {
    const response = await apiFetch("/api/studio/assets/upload", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json().catch(() => null) as Partial<StudioAssetUploadResponse> & { error?: string } | null;
    if (!response.ok || !payload?.success) {
      throw new Error(String(payload?.error || translator.tr("Could not upload the image.")));
    }
    return payload as StudioAssetUploadResponse;
  }, [translator]);

  const saveTemplateDefaults = useCallback(async () => {
    if (savingTemplate) return;
    setSavingTemplate(true);
    try {
      const payload = buildTemplateSettingsPayload(template);
      const response = await apiCall<{ success: boolean; template_defaults: Record<string, unknown> }>("/api/studio/template-settings", "POST", payload);
      const normalized = normalizeTemplateDefaults(response.template_defaults);
      setTemplate((currentTemplate) => ({
        ...currentTemplate,
        ...normalized,
      }));
      push(translator.tr("Template defaults saved."));
    } catch (error) {
      const message = error instanceof Error ? error.message : translator.tr("Could not save template defaults.");
      push(translator.maybeTr(message), "error");
    } finally {
      setSavingTemplate(false);
    }
  }, [push, savingTemplate, template, translator]);

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

  const handleMainImageUpload = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!current) {
      push(translator.tr("Create or open a draft before uploading a main image."), "error");
      return;
    }

    setUploadingMainImage(true);
    try {
      const contentId = current.id || await saveDraft();
      if (!contentId) {
        throw new Error(translator.tr("Could not prepare the draft for image upload."));
      }
      const formData = new FormData();
      formData.append("kind", "main-image");
      formData.append("content_id", contentId);
      formData.append("file", file);
      const uploaded = await uploadStudioAsset(formData);
      const nextPreviewUrl = resolveStudioImagePreviewUrl(
        String(uploaded.image_path || uploaded.image_url || uploaded.public_url || ""),
        contentId,
        String(uploaded.public_url || uploaded.image_url || ""),
      );
      setMainImagePreviewOverride(nextPreviewUrl);
      setCurrent((currentItem) => {
        if (!currentItem) return currentItem;
        return {
          ...currentItem,
          content_normalized: {
            ...currentItem.content_normalized,
            image_path: String(uploaded.image_path || uploaded.image_url || currentItem.content_normalized.image_path || ""),
          },
        };
      });
      await reloadStudio(contentId);
      push(translator.tr("Main image uploaded."));
    } catch (error) {
      const message = error instanceof Error ? error.message : translator.tr("Could not upload the main image.");
      push(translator.maybeTr(message), "error");
    } finally {
      setUploadingMainImage(false);
    }
  }, [current, push, reloadStudio, saveDraft, translator, uploadStudioAsset]);

  const handleMainImageRemove = useCallback(async () => {
    if (!current) return;

    setUploadingMainImage(true);
    try {
      if (current.id) {
        await apiCall(`/api/content/${current.id}`, "PUT", {
          image_path: "",
        });
      }
      setMainImagePreviewOverride("");
      setCurrent((currentItem) => {
        if (!currentItem) return currentItem;
        return {
          ...currentItem,
          content_normalized: {
            ...currentItem.content_normalized,
            image_path: "",
          },
        };
      });
      if (current.id) {
        await reloadStudio(current.id);
      }
      push(translator.tr("Main image removed."));
    } catch (error) {
      const message = error instanceof Error ? error.message : translator.tr("Could not remove the main image.");
      push(translator.maybeTr(message), "error");
    } finally {
      setUploadingMainImage(false);
    }
  }, [current, push, reloadStudio, translator]);

  const handleBackgroundImageUpload = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setUploadingBackgroundImage(true);
    try {
      const formData = new FormData();
      formData.append("kind", "background");
      formData.append("file", file);
      const uploaded = await uploadStudioAsset(formData);
      const nextTemplate = {
        ...template,
        backgroundImagePath: String(uploaded.backgroundImagePath || ""),
      };
      setTemplate(nextTemplate);
      const response = await apiCall<{ success: boolean; template_defaults: Record<string, unknown> }>(
        "/api/studio/template-settings",
        "POST",
        buildTemplateSettingsPayload(nextTemplate),
      );
      const normalized = normalizeTemplateDefaults(response.template_defaults);
      setTemplate((currentTemplate) => ({
        ...currentTemplate,
        ...normalized,
      }));
      push(translator.tr("Background uploaded and saved."));
    } catch (error) {
      const message = error instanceof Error ? error.message : translator.tr("Could not upload the background image.");
      push(translator.maybeTr(message), "error");
    } finally {
      setUploadingBackgroundImage(false);
    }
  }, [push, template, translator, uploadStudioAsset]);

  const handleBackgroundImageRemove = useCallback(async () => {
    const previousTemplate = template;
    const nextTemplate = {
      ...template,
      backgroundImagePath: "",
    };

    setUploadingBackgroundImage(true);
    setTemplate(nextTemplate);
    try {
      const response = await apiCall<{ success: boolean; template_defaults: Record<string, unknown> }>(
        "/api/studio/template-settings",
        "POST",
        buildTemplateSettingsPayload(nextTemplate),
      );
      const normalized = normalizeTemplateDefaults(response.template_defaults);
      setTemplate((currentTemplate) => ({
        ...currentTemplate,
        ...normalized,
      }));
      push(translator.tr("Background removed."));
    } catch (error) {
      setTemplate(previousTemplate);
      const message = error instanceof Error ? error.message : translator.tr("Could not remove the background image.");
      push(translator.maybeTr(message), "error");
    } finally {
      setUploadingBackgroundImage(false);
    }
  }, [push, template, translator]);

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
          topic: `${briefPrompt(brief, nicheMeta.label, nicheMeta.keywords, translator)}\n\n${buildTemplateAutomationNote(template, translator)}`,
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
  }, [brief, nicheMeta.keywords, nicheMeta.label, push, template, translator, withBusy]);

  const handleRegenerate = useCallback(async () => {
    if (!current) {
      push(translator.tr("Generate or open a draft before iterating it."), "error");
      return;
    }

    await withBusy(async () => {
      if (!hasMeaningfulContent(current)) {
        await handleGenerate();
        return;
      }

      const currentFormat = String(current.content_normalized.format || current.post_type || brief.format || "post").toLowerCase() as StudioBrief["format"];
      const result = await apiCall<{ success: boolean; content_id?: string | null; content: StudioItem["content_normalized"] }>(
        "/api/studio/regenerate",
          "POST",
        {
          content_id: current.id || undefined,
          format: currentFormat,
          content: current.content_normalized,
          instruction: `${regenerationPrompt(brief)}\n\n${buildTemplateAutomationNote(template, translator)}`,
          tone: brief.tone,
        },
        );
        setCurrent({
          ...current,
        post_type: currentFormat,
          content_normalized: {
            ...result.content,
          format: (result.content.format || currentFormat) as StudioBrief["format"],
            hashtags: Array.isArray(result.content.hashtags) ? result.content.hashtags : [],
            slides: Array.isArray(result.content.slides) ? result.content.slides : [],
            frames: Array.isArray(result.content.frames) ? result.content.frames : [],
            points: Array.isArray(result.content.points) ? result.content.points : [],
          },
        });
        push(translator.tr("Preview regenerated."));
    });
  }, [brief, current, handleGenerate, push, template, translator, withBusy]);

  const currentImagePath = String(current?.content_normalized.image_path || "").trim();
  const currentImagePreviewUrl = resolveStudioImagePreviewUrl(currentImagePath, current?.id, mainImagePreviewOverride);
  const backgroundImagePreviewUrl = template.backgroundImagePath.trim();
  const currentImageName = assetLabel(currentImagePath);
  const backgroundImageName = assetLabel(backgroundImagePreviewUrl);

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
  const activePreviewFormat = current ? currentFormat : brief.format;
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
    platformOptions.includes("instagram") && !page?.instagram_account_id ? {
      kind: "warn",
      title: translator.tr("Instagram missing"),
      copy: translator.tr("Instagram is selected for the current route, but the active page does not have an Instagram account linked."),
    } : null,
    platformOptions.includes("instagram") && activePreviewFormat === "post" && !String(current?.content_normalized.image_path || "").trim() ? {
      kind: "warn",
      title: translator.tr("Instagram media gap"),
      copy: translator.tr("Instagram post previews need an image path before the publish result will match the preview."),
    } : null,
    (activePreviewFormat === "story_sequence" || activePreviewFormat === "reel_script") ? {
      kind: "warn",
      title: translator.tr("Draft-only format"),
      copy: translator.tr("Story sequences and reel scripts stay export-first in V1. Save them as drafts rather than expecting auto-publish."),
    } : null,
  ].filter(Boolean) as Array<{ kind: string; title: string; copy: string }>;

  const workspaceCopy = !page
    ? translator.tr("Connect a Facebook page in Channels before publishing from Studio.")
    : translator.tr("Shape the brief, preview the output, and route the best draft into review.");
  const composerSections = [
    { id: "idea" as const, label: translator.tr("Idea"), copy: translator.tr("Brief and generation") },
    { id: "template" as const, label: translator.tr("Template"), copy: translator.tr("Brand and layout") },
    { id: "copy" as const, label: translator.tr("Copy"), copy: translator.tr("Refine the output") },
  ];

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
  const previewDraft = useMemo(() => {
    if (!current) return null;
    const hasImage = Boolean(String(current.content_normalized.image_path || "").trim());
    if (hasMeaningfulContent(current) || hasImage) {
      return current;
    }
    return null;
  }, [current]);
  const templatePreviewTitle = previewDraft
    ? (String(previewDraft.content_normalized.hook || "").trim() || translator.tr("Post hook"))
    : translator.tr("Your headline here");
  const templatePreviewSupport = previewDraft
    ? String(
      previewDraft.content_normalized.body
      || previewDraft.content_normalized.caption
      || previewDraft.content_normalized.cta
      || "",
    ).trim()
    : "";
  const previewMetrics = useMemo(() => {
    if (!currentContent) {
      return { reactions: "0", comments: "0", shares: "0" };
    }

    const metricSeed = previewSeed(
      `${page?.page_name || "Connected page"}:${previewSurface}:${currentFormat}:${String(currentContent.hook || "")}:${String(currentContent.body || currentContent.caption || currentContent.cta || "")}:${(currentContent.hashtags || []).join(" ")}`,
    );

    const reactions = 64 + (metricSeed % 540);
    const comments = 6 + (metricSeed % 44);
    const shares = 2 + (metricSeed % 18);

    return {
      reactions: compactMetric(reactions + shares),
      comments: compactMetric(comments),
      shares: compactMetric(shares),
    };
  }, [currentContent, currentFormat, page?.page_name, previewSurface]);

  const templateBackgroundSection = (
    <section className="cf-studio-template-group">
      <div className="cf-studio-template-group-head">
        <div className="cf-studio-mini-kicker">{translator.tr("Background image")}</div>
        <p className="cf-inline-note">{translator.tr("Use a background image as the first template layer behind the main image and title.")}</p>
      </div>
      <div className="cf-studio-template-grid is-media">
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-background-density">{translator.tr("Background intensity")}</label>
          <input
            id="cf-studio-template-background-density"
            className="cf-input"
            type="range"
            min="0"
            max="100"
            step="5"
            value={template.backgroundDensity}
            onChange={(event) => setTemplateField("backgroundDensity", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.backgroundDensity}%</div>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-background-zoom">{translator.tr("Background zoom")}</label>
          <input
            id="cf-studio-template-background-zoom"
            className="cf-input"
            type="range"
            min="40"
            max="180"
            step="5"
            value={template.backgroundZoom}
            onChange={(event) => setTemplateField("backgroundZoom", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.backgroundZoom}%</div>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-background-offset-x">{translator.tr("Background horizontal align")}</label>
          <input
            id="cf-studio-template-background-offset-x"
            className="cf-input"
            type="range"
            min="-40"
            max="40"
            step="2"
            value={template.backgroundOffsetX}
            onChange={(event) => setTemplateField("backgroundOffsetX", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.backgroundOffsetX}%</div>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-background-offset-y">{translator.tr("Background vertical align")}</label>
          <input
            id="cf-studio-template-background-offset-y"
            className="cf-input"
            type="range"
            min="-40"
            max="40"
            step="2"
            value={template.backgroundOffsetY}
            onChange={(event) => setTemplateField("backgroundOffsetY", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.backgroundOffsetY}%</div>
        </div>
      </div>
    </section>
  );

  const templateAssetSection = (
    <section className="cf-studio-template-group cf-studio-template-group-assets">
      <div className="cf-studio-template-group-head">
        <div className="cf-studio-mini-kicker">{translator.tr("Media assets")}</div>
        <p className="cf-inline-note">{translator.tr("Upload both visuals directly from your computer, then fine-tune their framing below.")}</p>
      </div>
      <div className="cf-studio-template-asset-actions">
        <NeonButton type="button" variant="ghost" className="cf-studio-inline-action" onClick={() => focusEditorField(mainImageInputRef)}>
          {translator.tr("Add main image")}
        </NeonButton>
        <NeonButton type="button" variant="ghost" className="cf-studio-inline-action" onClick={() => focusEditorField(backgroundImageInputRef)}>
          {translator.tr("Add background")}
        </NeonButton>
      </div>
      <div className="cf-studio-template-upload-row">
        <div className="cf-field cf-studio-upload-field">
          <label className="cf-field-label" htmlFor="cf-studio-editor-image2">{translator.tr("Main image")}</label>
          <input
            ref={mainImageInputRef}
            id="cf-studio-editor-image2"
            className="cf-upload-input-native"
            type="file"
            accept="image/*"
            onChange={handleMainImageUpload}
          />
          <label className={`cf-upload-tile ${currentImagePreviewUrl ? "is-filled" : ""}`} htmlFor="cf-studio-editor-image2" aria-busy={uploadingMainImage}>
            <span className="cf-upload-tile-badge">
              {uploadingMainImage ? translator.tr("Uploading...") : currentImagePreviewUrl ? translator.tr("Uploaded") : translator.tr("From computer")}
            </span>
            <div className="cf-upload-tile-body">
              {currentImagePreviewUrl ? (
                <>
                  <img className="cf-upload-tile-preview" src={currentImagePreviewUrl} alt={translator.tr("Main image preview")} />
                  <div className="cf-upload-tile-overlay">
                    <strong>{translator.tr("Replace main image")}</strong>
                    <span>{translator.tr("Choose another file from your computer.")}</span>
                  </div>
                </>
              ) : (
                <div className="cf-upload-tile-empty">
                  <strong>{translator.tr("Upload main image")}</strong>
                  <span>{translator.tr("Choose the foreground publication image directly from your computer.")}</span>
                </div>
              )}
            </div>
          </label>
          <div className="cf-upload-meta">
            <span className="cf-inline-note">{currentImageName || translator.tr("No main image uploaded yet.")}</span>
            <div className="cf-upload-meta-actions">
              <label className="cf-upload-link" htmlFor="cf-studio-editor-image2">{translator.tr("Choose file")}</label>
              {currentImagePreviewUrl ? (
                <button type="button" className="cf-upload-clear" onClick={handleMainImageRemove} disabled={uploadingMainImage}>
                  {translator.tr("Remove")}
                </button>
              ) : null}
            </div>
          </div>
        </div>
        <div className="cf-field cf-studio-upload-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-background-image">{translator.tr("Background image")}</label>
          <input
            ref={backgroundImageInputRef}
            id="cf-studio-template-background-image"
            className="cf-upload-input-native"
            type="file"
            accept="image/*"
            onChange={handleBackgroundImageUpload}
          />
          <label className={`cf-upload-tile ${backgroundImagePreviewUrl ? "is-filled" : ""}`} htmlFor="cf-studio-template-background-image" aria-busy={uploadingBackgroundImage}>
            <span className="cf-upload-tile-badge">
              {uploadingBackgroundImage ? translator.tr("Uploading...") : backgroundImagePreviewUrl ? translator.tr("Saved") : translator.tr("From computer")}
            </span>
            <div className="cf-upload-tile-body">
              {backgroundImagePreviewUrl ? (
                <>
                  <img className="cf-upload-tile-preview" src={backgroundImagePreviewUrl} alt={translator.tr("Background image preview")} />
                  <div className="cf-upload-tile-overlay">
                    <strong>{translator.tr("Replace background")}</strong>
                    <span>{translator.tr("Choose another background file from your computer.")}</span>
                  </div>
                </>
              ) : (
                <div className="cf-upload-tile-empty">
                  <strong>{translator.tr("Upload background")}</strong>
                  <span>{translator.tr("Choose the base background layer for the template.")}</span>
                </div>
              )}
            </div>
          </label>
          <div className="cf-upload-meta">
            <span className="cf-inline-note">{backgroundImageName || translator.tr("No background uploaded yet.")}</span>
            <div className="cf-upload-meta-actions">
              <label className="cf-upload-link" htmlFor="cf-studio-template-background-image">{translator.tr("Choose file")}</label>
              {backgroundImagePreviewUrl ? (
                <button type="button" className="cf-upload-clear" onClick={handleBackgroundImageRemove} disabled={uploadingBackgroundImage}>
                  {translator.tr("Remove")}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </section>
  );

  const templateMediaSection = (
    <section className="cf-studio-template-group">
      <div className="cf-studio-template-group-head">
        <div className="cf-studio-mini-kicker">{translator.tr("Foreground image")}</div>
        <p className="cf-inline-note">{translator.tr("Control the main image framing, scale, clarity, and placement inside the template.")}</p>
      </div>
      <div className="cf-studio-template-grid is-media">
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-media-fit">{translator.tr("Crop mode")}</label>
          <select
            id="cf-studio-template-media-fit"
            className="cf-select"
            value={template.mediaFit}
            onChange={(event) => setTemplateField("mediaFit", event.target.value as StudioTemplateDesign["mediaFit"])}
          >
            <option value="contain">{translator.tr("Contain")}</option>
            <option value="cover">{translator.tr("Cover")}</option>
          </select>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-image-width">{translator.tr("Image width")}</label>
          <input
            id="cf-studio-template-image-width"
            className="cf-input"
            type="range"
            min="40"
            max="100"
            step="2"
            value={template.mediaWidth}
            onChange={(event) => setTemplateField("mediaWidth", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.mediaWidth}%</div>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-image-height">{translator.tr("Image height")}</label>
          <input
            id="cf-studio-template-image-height"
            className="cf-input"
            type="range"
            min="110"
            max="260"
            step="5"
            value={template.mediaHeight}
            onChange={(event) => setTemplateField("mediaHeight", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.mediaHeight}px</div>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-media-clarity">{translator.tr("Image clarity")}</label>
          <input
            id="cf-studio-template-media-clarity"
            className="cf-input"
            type="range"
            min="80"
            max="140"
            step="5"
            value={template.mediaClarity}
            onChange={(event) => setTemplateField("mediaClarity", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.mediaClarity}%</div>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-media-offset-x">{translator.tr("Horizontal align")}</label>
          <input
            id="cf-studio-template-media-offset-x"
            className="cf-input"
            type="range"
            min="-60"
            max="60"
            step="2"
            value={template.mediaOffsetX}
            onChange={(event) => setTemplateField("mediaOffsetX", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.mediaOffsetX}%</div>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-media-offset-y">{translator.tr("Vertical align")}</label>
          <input
            id="cf-studio-template-media-offset-y"
            className="cf-input"
            type="range"
            min="-60"
            max="60"
            step="2"
            value={template.mediaOffsetY}
            onChange={(event) => setTemplateField("mediaOffsetY", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.mediaOffsetY}%</div>
        </div>
        <div className="cf-field cf-field-span">
          <label className="cf-field-label" htmlFor="cf-studio-template-media-zoom">{translator.tr("Zoom")}</label>
          <input
            id="cf-studio-template-media-zoom"
            className="cf-input"
            type="range"
            min="40"
            max="220"
            step="5"
            value={template.mediaZoom}
            onChange={(event) => setTemplateField("mediaZoom", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.mediaZoom}%</div>
        </div>
      </div>
    </section>
  );

  const templateTitleSection = (
    <section className="cf-studio-template-group">
      <div className="cf-studio-template-group-head">
        <div className="cf-studio-mini-kicker">{translator.tr("Title treatment")}</div>
        <p className="cf-inline-note">{translator.tr("Make the title easier to read inside the creative before sending the draft to the agent.")}</p>
      </div>
      <div className="cf-studio-template-grid is-media">
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-title-scale">{translator.tr("Title size")}</label>
          <input
            id="cf-studio-template-title-scale"
            className="cf-input"
            type="range"
            min="80"
            max="140"
            step="5"
            value={template.titleScale}
            onChange={(event) => setTemplateField("titleScale", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.titleScale}%</div>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-title-font">{translator.tr("Title font")}</label>
          <select
            id="cf-studio-template-title-font"
            className="cf-select"
            value={template.titleFontFamily}
            onChange={(event) => setTemplateField("titleFontFamily", event.target.value as StudioTemplateDesign["titleFontFamily"])}
          >
            <option value="display">{translator.tr("Display")}</option>
            <option value="body">{translator.tr("Body")}</option>
            <option value="mono">{translator.tr("Mono")}</option>
          </select>
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-title-color">{translator.tr("Title color")}</label>
          <input
            id="cf-studio-template-title-color"
            className="cf-input cf-input-color"
            type="color"
            value={template.titleColor}
            onChange={(event) => setTemplateField("titleColor", event.target.value)}
          />
        </div>
        <div className="cf-field">
          <label className="cf-field-label" htmlFor="cf-studio-template-title-width">{translator.tr("Title width")}</label>
          <input
            id="cf-studio-template-title-width"
            className="cf-input"
            type="range"
            min="68"
            max="100"
            step="2"
            value={template.titleWidth}
            onChange={(event) => setTemplateField("titleWidth", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.titleWidth}%</div>
        </div>
        <div className="cf-field cf-field-span">
          <label className="cf-field-label" htmlFor="cf-studio-template-title-offset-y">{translator.tr("Title vertical align")}</label>
          <input
            id="cf-studio-template-title-offset-y"
            className="cf-input"
            type="range"
            min="-24"
            max="24"
            step="2"
            value={template.titleOffsetY}
            onChange={(event) => setTemplateField("titleOffsetY", Number(event.target.value))}
          />
          <div className="cf-inline-note">{template.titleOffsetY}px</div>
        </div>
      </div>
    </section>
  );

  const templateBuilderCard = (
    <article
      id="cf-studio-panel-template"
      role="tabpanel"
      aria-labelledby="cf-studio-tab-template"
      className="cf-card cf-panel cf-studio-template-card"
      hidden={!desktopCanvas && composerSection !== "template"}
      aria-hidden={!desktopCanvas && composerSection !== "template"}
    >
      <div className="cf-studio-panel-head cf-studio-panel-head-simple">
        <div className="cf-studio-panel-copy">
          <div className="cf-studio-mini-kicker">{translator.tr("Template builder")}</div>
          <h2 className="cf-studio-panel-title">{translator.tr("Shape the creative system")}</h2>
          <p className="cf-inline-note">{translator.tr("Lock the brand markers, framing, and reusable layout defaults that guide every new draft.")}</p>
        </div>
        <NeonButton variant="ghost" busy={savingTemplate} onClick={() => void saveTemplateDefaults()}>
          {savingTemplate ? translator.tr("Saving...") : translator.tr("Save Template")}
        </NeonButton>
      </div>

      <div className="cf-studio-template-groups">
        <button
          type="button"
          className={`cf-brief-toggle ${advancedPanels.brand ? "is-open" : ""}`}
          onClick={() => toggleAdvancedPanel("brand")}
        >
          <span className="cf-brief-toggle-text">{translator.tr("Brand settings")}</span>
          <span className="cf-brief-toggle-icon">{advancedPanels.brand ? "-" : "+"}</span>
        </button>
        <div className={`cf-brief-advanced ${advancedPanels.brand ? "is-open" : ""}`}>
          <section className="cf-studio-template-group">
            <div className="cf-studio-template-group-head">
              <div className="cf-studio-mini-kicker">{translator.tr("Brand")}</div>
              <p className="cf-inline-note">{translator.tr("Set the identity markers that should stay stable across every template.")}</p>
            </div>
            <div className="cf-studio-template-grid">
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-studio-template-brand">{translator.tr("Brand or page name")}</label>
                <input
                  id="cf-studio-template-brand"
                  className="cf-input"
                  type="text"
                  value={template.brandName}
                  onChange={(event) => setTemplateField("brandName", event.target.value)}
                />
              </div>
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-studio-template-handle">{translator.tr("Handle")}</label>
                <input
                  id="cf-studio-template-handle"
                  className="cf-input"
                  type="text"
                  value={template.socialHandle}
                  onChange={(event) => setTemplateField("socialHandle", event.target.value)}
                />
              </div>
              <label className="cf-choice-card cf-studio-toggle-card">
                <input
                  className="cf-choice-input"
                  type="checkbox"
                  checked={template.showSocialStrip}
                  onChange={(event) => setTemplateField("showSocialStrip", event.target.checked)}
                />
                <div className="cf-choice-copy">
                  <strong>{translator.tr("Show social row")}</strong>
                  <small>{translator.tr("Add social icons and the creator handle across the template.")}</small>
                </div>
              </label>
              <label className="cf-choice-card cf-studio-toggle-card">
                <input
                  className="cf-choice-input"
                  type="checkbox"
                  checked={template.showBrandBadge}
                  onChange={(event) => setTemplateField("showBrandBadge", event.target.checked)}
                />
                <div className="cf-choice-copy">
                  <strong>{translator.tr("Show brand chip")}</strong>
                  <small>{translator.tr("Display the small badge on the right side of the brand row.")}</small>
                </div>
              </label>
              <label className="cf-choice-card cf-studio-toggle-card">
                <input
                  className="cf-choice-input"
                  type="checkbox"
                  checked={template.mediaFullBleed}
                  onChange={(event) => setTemplateField("mediaFullBleed", event.target.checked)}
                />
                <div className="cf-choice-copy">
                  <strong>{translator.tr("Full-picture mode")}</strong>
                  <small>{translator.tr("Main image fills the entire template edge to edge, with text overlaid on top.")}</small>
                </div>
              </label>
            </div>
          </section>
        </div>

        <button
          type="button"
          className={`cf-brief-toggle ${advancedPanels.layout ? "is-open" : ""}`}
          onClick={() => toggleAdvancedPanel("layout")}
        >
          <span className="cf-brief-toggle-text">{translator.tr("Layout controls")}</span>
          <span className="cf-brief-toggle-icon">{advancedPanels.layout ? "-" : "+"}</span>
        </button>
        <div className={`cf-brief-advanced ${advancedPanels.layout ? "is-open" : ""}`}>
          <section className="cf-studio-template-group">
            <div className="cf-studio-template-group-head">
              <div className="cf-studio-mini-kicker">{translator.tr("Layout")}</div>
              <p className="cf-inline-note">{translator.tr("Keep the template background soft so the image and title remain readable.")}</p>
            </div>
            <div className="cf-studio-template-grid">
              <div className="cf-field cf-field-span">
                <div className="cf-inline-note">{translator.tr("Image paths are managed in the Studio draft editor. Use the controls here only for framing and alignment.")}</div>
              </div>
            </div>
          </section>
        </div>

        {!desktopCanvas ? (
          <>
            <button
              type="button"
              className={`cf-brief-toggle ${advancedPanels.media ? "is-open" : ""}`}
              onClick={() => toggleAdvancedPanel("media")}
            >
              <span className="cf-brief-toggle-text">{translator.tr("Media advanced controls")}</span>
              <span className="cf-brief-toggle-icon">{advancedPanels.media ? "-" : "+"}</span>
            </button>
            <div className={`cf-brief-advanced ${advancedPanels.media ? "is-open" : ""}`}>
              {templateBackgroundSection}
              {templateMediaSection}
              {templateTitleSection}
            </div>
          </>
        ) : null}
      </div>
    </article>
  );

  const studioInsightsPanel = (
    <article className="cf-card cf-panel cf-studio-template-media-card">
      <div className="cf-studio-panel-head cf-studio-panel-head-simple">
        <div className="cf-studio-panel-copy">
          <div className="cf-studio-mini-kicker">{translator.tr("Agent plan")}</div>
          <h3 className="cf-studio-panel-title">{translator.tr("Quick creative cues")}</h3>
          <p className="cf-inline-note">{translator.tr("What the agent understands from your current parameters.")}</p>
        </div>
      </div>
      <div className="cf-studio-template-groups">
        <div id="cf-studio-brief-summary" className="cf-studio-insights-inline" aria-live="polite">
          {insightCards.map((card, i) => (
            <motion.article
              key={card.title}
              className="cf-insight-card"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
            >
              <div className="cf-insight-title">{card.title}</div>
              <div className="cf-insight-value">{card.value}</div>
              <div className="cf-insight-copy">{card.copy}</div>
            </motion.article>
          ))}
        </div>
      </div>
    </article>
  );

  return (
    <section
      className="cf-screen cf-studio-page"
      data-cf-studio=""
      data-cf-studio-owned="split"
      data-studio-layout={studioLayout}
    >
      <section className="cf-studio-shell" data-library-open={String(libraryOpen)} aria-label={translator.tr("Studio")}>
        {libraryOpen ? (
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

        <div className="cf-studio-workarea">
          <div
            ref={stageRef}
            className={[
              "cf-studio-stage",
              desktopCanvas ? "is-desktop-canvas" : "",
              centeredCanvasDesktop ? "is-centered-canvas" : "",
              desktopCanvas && !centeredCanvasDesktop ? "is-preview-right-canvas" : "",
            ].filter(Boolean).join(" ")}
          >
          {loading && !payload ? (
              <div className="cf-studio-dashboard" aria-busy="true">
              <ShimmerSkeleton lines={8} />
              <ShimmerSkeleton lines={8} />
              <ShimmerSkeleton lines={5} />
            </div>
          ) : null}
            <div className="cf-studio-dashboard">
              <div className={`cf-studio-canvas-intro ${desktopCanvas ? "cf-studio-sr-only" : ""}`}>
              <div className="cf-studio-mini-kicker">{translator.tr("Studio canvas")}</div>
              <motion.h1
                className="cf-studio-canvas-title"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
              >
                {translator.tr("Design, test, and route every post")}
              </motion.h1>
                <p className="cf-inline-note cf-studio-canvas-copy">{workspaceCopy}</p>
            </div>

              <div className="cf-studio-canvas-middle">
                <div className="cf-studio-preview-topbar">
                  <div className="cf-surface-switcher" id="cf-studio-preview-tabs" aria-label={translator.tr("Preview surface")}>
                    {platformOptions.map((surface) => (
                      <button
                        key={surface}
                        type="button"
                        className={`cf-surface-switch-btn ${previewSurface === surface ? "is-active" : ""}`}
                        aria-label={translator.tr(surface === "instagram" ? "Instagram preview" : "Facebook preview")}
                        title={translator.tr(surface === "instagram" ? "Instagram preview" : "Facebook preview")}
                        onClick={() => setPreviewSurface(surface as "facebook" | "instagram")}
                      >
                        <i className={surface === "instagram" ? "fa-brands fa-instagram" : "fa-brands fa-facebook-f"} aria-hidden="true" />
                        <span className="cf-surface-switch-text">{translator.tr(surface === "instagram" ? "Instagram" : "Facebook")}</span>
                      </button>
                    ))}
                  </div>
                  <NeonButton
                    type="button"
                    variant="ghost"
                    className="cf-studio-template-expand-btn"
                    onClick={() => setTemplatePreviewOpen(true)}
                    disabled={!previewDraft}
                  >
                    {translator.tr("Expand template")}
                  </NeonButton>
                </div>
              </div>

            <div className="cf-studio-canvas-controls">
              <div className="cf-studio-canvas-actions">
                <button type="button" className="cf-btn-ghost cf-studio-head-drawer" id="cf-studio-library-toggle" onClick={() => setLibraryOpen((currentOpen) => !currentOpen)}>
                  <span>{translator.tr("Library")}</span>
                  <span id="cf-studio-library-count" className="cf-studio-head-count">{filteredItems.length}</span>
                </button>
                <NeonButton
                  id="cf-studio-new-draft"
                  onClick={() => {
                    setCurrent(createBlankDraft(brief));
                    setFeedback(translator.tr("New draft started. Build the brief, run the AI preview, then decide what reaches the queue."));
                    setLibraryOpen(false);
                  }}
                >
                  {translator.tr("New Draft")}
                </NeonButton>
              </div>
              <div className="cf-studio-canvas-statusline">
                <span className="cf-studio-stat-pill">{translator.tr("{count} drafts", { count: String(collections.drafts.length) })}</span>
                <span className="cf-studio-stat-pill">{translator.tr("{count} in review", { count: String(collections.review.length) })}</span>
                <span className={`cf-studio-status-chip ${page ? "is-ready" : "is-warn"}`}>{activeStatus}</span>
              </div>
            </div>

              <div className="cf-studio-dashboard-column cf-studio-left-column">
          {!desktopCanvas ? (
          <div className="cf-studio-section-switcher" role="tablist" aria-label={translator.tr("Studio sections")}>
            {composerSections.map(({ id: sectionId, label, copy }) => (
              <button
                key={sectionId}
                type="button"
                className={`cf-studio-section-tab ${composerSection === sectionId ? "is-active" : ""}`}
                id={`cf-studio-tab-${sectionId}`}
                role="tab"
                aria-selected={composerSection === sectionId ? "true" : "false"}
                aria-controls={`cf-studio-panel-${sectionId}`}
                tabIndex={composerSection === sectionId ? 0 : -1}
                onClick={() => setComposerSection(sectionId)}
              >
                <strong>{label}</strong>
                <span>{copy}</span>
              </button>
            ))}
          </div>
          ) : null}
          <article
            id="cf-studio-panel-idea"
            role="tabpanel"
            aria-labelledby="cf-studio-tab-idea"
            className="cf-card cf-panel cf-studio-composer-card mt-[107px] mb-[107px]"
            hidden={!desktopCanvas && composerSection !== "idea"}
            aria-hidden={!desktopCanvas && composerSection !== "idea"}
          >
            <div className="cf-studio-panel-head cf-studio-panel-head-simple">
              <div className="cf-studio-panel-copy">
                <div className="cf-studio-mini-kicker">{translator.tr("1. Creator brief")}</div>
                <h2 className="cf-studio-panel-title">{translator.tr("Refine your content generation inputs")}</h2>
                <p className="cf-inline-note">{translator.tr("Keep the prompt inputs focused here before generating or iterating the draft.")}</p>
              </div>
              <div className="cf-inline-actions cf-studio-brief-toolbar">
                <NeonButton id="cf-studio-generate" glow busy={busy} onClick={() => void handleGenerate()} disabled={busy}>
                  {busy ? translator.tr("Working...") : translator.tr("Run AI Preview")}
                </NeonButton>
                <NeonButton variant="ghost" id="cf-studio-regenerate" busy={busy} onClick={() => void handleRegenerate()} disabled={busy}>
                  {busy ? translator.tr("Working...") : translator.tr("Iterate Preview")}
                </NeonButton>
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

          {desktopCanvas ? (
            <>
              {studioInsightsPanel}
              {templateBuilderCard}
            </>
          ) : templateBuilderCard}

                </div>

              <div className="cf-studio-dashboard-column cf-studio-center-column">
                <div className="cf-studio-preview-stack">
                  {warningItems.length ? (
                    <div className="cf-studio-warning-rail">
                      {warningItems.slice(0, 3).map((warning) => (
                        <div key={`${warning.kind}-${warning.title}`} className={`cf-warning-item ${warning.kind}`}>
                          <div>
                            <div className="cf-warning-title">{warning.title}</div>
                            <div>{warning.copy}</div>
                </div>
                  </div>
                      ))}
                  </div>
                  ) : null}
                  <article className="cf-card cf-panel cf-studio-preview-shell pt-[-8px] mt-[-31px] mb-[-31px]">
                    <div id="cf-studio-preview-card" className="cf-phone-mockup-wrap" aria-live="polite">
                      <div className="cf-phone-frame">
                        <div className="cf-phone-notch" />
                        <div className="cf-phone-screen">
                          <PhoneStatusBar dark={previewSurface === "instagram"} />
                          <div className="cf-phone-screen-inner">
                            {previewDraft ? (
                              <PreviewBody
                                current={previewDraft}
                                surface={previewSurface}
                                translator={translator}
                                pageName={page?.page_name || translator.tr("Connected page")}
                                briefPlatformLabel={platformLabel(previewDraft.platforms || brief.platform, translator)}
                                template={template}
                                mediaUrl={currentImagePreviewUrl}
                              />
                            ) : (
                              <EmptyState title={translator.tr("Preview unavailable")} copy={translator.tr("Run the AI preview or open a draft to inspect the final publish surface.")} />
                            )}
                </div>
                  </div>
                        <div className="cf-phone-home-bar" />
                  </div>
            </div>
          </article>
                </div>
              </div>

              <div className="cf-studio-dashboard-column cf-studio-right-column">
            <article
              id="cf-studio-panel-copy"
              role="tabpanel"
              aria-labelledby="cf-studio-tab-copy"
              className="cf-card cf-panel cf-studio-editor-card"
                  hidden={!desktopCanvas && composerSection !== "copy"}
                  aria-hidden={!desktopCanvas && composerSection !== "copy"}
            >
              <div className="cf-studio-panel-head cf-studio-panel-head-simple">
                <div className="cf-studio-panel-copy">
                  <div className="cf-studio-mini-kicker">{translator.tr("2. Studio draft editor")}</div>
                  <h2 className="cf-studio-panel-title">{translator.tr("Adjust the content")}</h2>
                  <p className="cf-inline-note">{translator.tr("Edit the final text content and the preview media controls inside one panel.")}</p>
                </div>
              </div>
              <div id="cf-studio-editor" className="cf-studio-editor-body" aria-live="polite">
                {busy ? (
                  <ShimmerSkeleton lines={6} />
                ) : current ? (
                  <div className="cf-studio-workbench">
                    {(currentFormat === "post" || currentFormat === "carousel") ? templateAssetSection : null}
                    <div className="cf-studio-mini-kicker">{translator.tr("Text content")}</div>
                    {(currentFormat === "post" || currentFormat === "reel_script") ? (
                      <div className="cf-field">
                        <label className="cf-field-label" htmlFor="cf-studio-editor-hook2">{translator.tr(currentFormat === "reel_script" ? "Reel hook" : "Hook")}</label>
                        <textarea id="cf-studio-editor-hook2" className="cf-textarea cf-textarea-sm" rows={2} value={currentContent?.hook || ""} onChange={(event) => setCurrentTextField("hook", event.target.value)} />
                      </div>
                    ) : null}
                    {currentFormat === "post" ? (
                      <div className="cf-field">
                        <label className="cf-field-label" htmlFor="cf-studio-editor-body2">{translator.tr("Body")}</label>
                        <textarea id="cf-studio-editor-body2" className="cf-textarea" rows={6} value={currentContent?.body || ""} onChange={(event) => setCurrentTextField("body", event.target.value)} />
                      </div>
                    ) : null}
                    {currentFormat === "carousel" ? (
                      <>
                        <div className="cf-field">
                          <label className="cf-field-label" htmlFor="cf-studio-editor-caption2">{translator.tr("Caption")}</label>
                          <textarea id="cf-studio-editor-caption2" className="cf-textarea cf-textarea-sm" rows={3} value={currentContent?.caption || ""} onChange={(event) => setCurrentTextField("caption", event.target.value)} />
                        </div>
                        <div className="cf-field">
                          <label className="cf-field-label" htmlFor="cf-studio-editor-slides2">{translator.tr("Carousel")}</label>
                          <textarea id="cf-studio-editor-slides2" className="cf-textarea" rows={6} placeholder="Headline | Body" value={carouselSlidesText} onChange={(event) => setCurrentSlidesFromText(event.target.value)} />
                        </div>
                      </>
                    ) : null}
                    {currentFormat === "story_sequence" ? (
                      <div className="cf-field">
                        <label className="cf-field-label" htmlFor="cf-studio-editor-frames2">{translator.tr("Story sequence")}</label>
                        <textarea id="cf-studio-editor-frames2" className="cf-textarea" rows={6} value={storyFramesText} onChange={(event) => setCurrentFramesFromText(event.target.value)} />
                      </div>
                    ) : null}
                    {currentFormat === "reel_script" ? (
                      <div className="cf-field">
                        <label className="cf-field-label" htmlFor="cf-studio-editor-points2">{translator.tr("Proof points and key points")}</label>
                        <textarea id="cf-studio-editor-points2" className="cf-textarea" rows={6} value={reelPointsText} onChange={(event) => setCurrentPointsFromText(event.target.value)} />
                      </div>
                    ) : null}
                    {(currentFormat === "post" || currentFormat === "reel_script") ? (
                      <div className="cf-field">
                        <label className="cf-field-label" htmlFor="cf-studio-editor-cta2">{translator.tr("Closing CTA")}</label>
                        <textarea id="cf-studio-editor-cta2" className="cf-textarea cf-textarea-sm" rows={2} value={currentContent?.cta || ""} onChange={(event) => setCurrentTextField("cta", event.target.value)} />
                      </div>
                    ) : null}
                    {desktopCanvas ? (
                      <div className="cf-studio-template-groups cf-studio-template-groups-media">
                        {currentFormat !== "post" && currentFormat !== "carousel" ? templateAssetSection : null}
                        {templateBackgroundSection}
                        {templateMediaSection}
                        {templateTitleSection}
                        </div>
                      ) : null}
                  </div>
                ) : (
                  <EmptyState title={translator.tr("No draft selected")} copy={translator.tr("Choose an item from the library or create a new draft.")} />
                )}
              </div>
            </article>
            </div>

              <div className="cf-studio-dashboard-column cf-studio-finalize-column">
          <div className="cf-studio-canvas-foot">
            <article className="cf-card cf-panel cf-studio-publish-card">
              <div className="cf-studio-panel-head cf-studio-panel-head-simple">
                <div className="cf-studio-panel-copy">
                  <div className="cf-studio-mini-kicker">{translator.tr("3. Scheduling & finalizing")}</div>
                  <h2 className="cf-studio-panel-title">{translator.tr("Schedule & publish")}</h2>
                  <p className="cf-inline-note">{translator.tr("Finalize hashtags, routing, and timing before the draft leaves Studio.")}</p>
                </div>
              </div>
              <div className="cf-studio-canvas-foot-grid">
                <div className="cf-studio-foot-primary">
                  <div className="cf-field">
                    <label className="cf-field-label" htmlFor="cf-studio-editor-hashtags2">{translator.tr("Hashtags")}</label>
                    <input id="cf-studio-editor-hashtags2" className="cf-input" type="text" value={editorHashtags} onChange={(event) => setCurrentHashtags(event.target.value)} />
                      </div>
                  <div className="cf-field">
                    <label className="cf-field-label" htmlFor="cf-studio-platform-finalize">{translator.tr("Publish route")}</label>
                    <select id="cf-studio-platform-finalize" className="cf-select" value={brief.platform} onChange={(event) => setBriefField("platform", event.target.value)}>
                      <option value="facebook">{translator.tr("Facebook only")}</option>
                      <option value="facebook,instagram">{translator.tr("Facebook + Instagram")}</option>
                      <option value="instagram">{translator.tr("Instagram only")}</option>
                    </select>
                    </div>
                  <div className="cf-field cf-studio-foot-schedule">
                    <label className="cf-field-label" htmlFor="cf-studio-schedule">{translator.tr("Scheduled time")}</label>
                    <input id="cf-studio-schedule" className="cf-input" type="datetime-local" value={brief.schedule} onChange={(event: ChangeEvent<HTMLInputElement>) => setBriefField("schedule", event.target.value)} />
                      </div>
                  <div className="cf-field">
                    <label className="cf-field-label" htmlFor="cf-studio-timezone">{translator.tr("Timezone")}</label>
                    <input id="cf-studio-timezone" className="cf-input" type="text" readOnly value={Intl.DateTimeFormat().resolvedOptions().timeZone} />
                      </div>
                  <div className="cf-studio-publish-summary">
                    <div className="cf-studio-publish-reactions">
                      <div className="cf-social-reaction-badges" aria-hidden="true">
                        <span className="is-like">👍</span>
                        <span className="is-love">❤</span>
                    </div>
                      <div className="cf-studio-publish-reactions-copy">
                        <strong>{previewMetrics.reactions}</strong>
                        <span>{translator.tr("reactions")}</span>
                  </div>
                  </div>
                    <div className="cf-studio-publish-inline-actions">
                      <NeonButton className="cf-studio-inline-action" variant="ghost" id="cf-studio-secondary-action" busy={busy} onClick={() => void handleSecondaryAction()} disabled={busy || secondaryDisabled}>
                      {busy ? translator.tr("Working...") : secondaryLabel}
                    </NeonButton>
                      <NeonButton className="cf-studio-inline-action" variant="ghost" id="cf-studio-tertiary-action" busy={busy} onClick={() => void handleTertiaryAction()} disabled={busy}>
                      {busy ? translator.tr("Working...") : tertiaryLabel}
                    </NeonButton>
                  </div>
                </div>
                  <div className="cf-action-stack cf-studio-publish-actions">
                    <NeonButton className="cf-studio-primary-cta" id="cf-studio-primary-action" glow busy={busy} onClick={() => void handlePrimaryAction()} disabled={busy}>
                      {busy ? translator.tr("Working...") : primaryLabel}
                    </NeonButton>
                  </div>
                </div>
              </div>
            </article>
                </div>
              </div>

            </div>
          </div>
        </div>
      </section>

      <AnimatePresence>
        {templatePreviewOpen ? (
          <motion.div
            className="cf-template-preview-modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setTemplatePreviewOpen(false)}
          >
            <motion.section
              className="cf-template-preview-modal"
              role="dialog"
              aria-modal="true"
              aria-label={translator.tr("Expanded template preview")}
              initial={{ opacity: 0, y: 24, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="cf-template-preview-modal-head">
                <div className="cf-template-preview-modal-copy">
                  <div className="cf-studio-mini-kicker">{translator.tr("Template preview")}</div>
                  <h2>{translator.tr("Inspect the creative larger")}</h2>
                  <p>{translator.tr("Review the background, hero image, title, and brand row before saving the template.")}</p>
                </div>
                <button type="button" className="cf-btn-ghost cf-template-preview-close" onClick={() => setTemplatePreviewOpen(false)}>
                  {translator.tr("Close")}
                </button>
              </div>
              <div className="cf-template-preview-modal-stage">
                <div className="cf-template-preview-modal-canvas">
                  <TemplateCanvas
                    surface={previewSurface}
                    pageName={page?.page_name || translator.tr("Connected page")}
                    translator={translator}
                    template={template}
                    fallbackMediaUrl={currentImagePreviewUrl}
                    titleText={templatePreviewTitle}
                    supportText={templatePreviewSupport}
                  />
                </div>
              </div>
            </motion.section>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {error && !loading && !payload ? (
        <article className="cf-card cf-panel">
          <ErrorState title={translator.tr("Something failed to load")} copy={translator.maybeTr(error)} />
        </article>
      ) : null}
    </section>
  );
}
