import { useEffect, useMemo, useState } from "react";

import { apiCall, BootstrapResponse } from "../lib/api";
import { BootPayload } from "../lib/boot";
import { Translator } from "../lib/i18n";
import { EmptyState, ErrorState } from "../ui/States";
import { useToast } from "../ui/ToastProvider";

type ChannelsProps = {
  boot: BootPayload;
  translator: Translator;
  loading: boolean;
  error: string | null;
  payload: BootstrapResponse | null;
  refresh: (force?: boolean) => Promise<BootstrapResponse | null>;
};

type PageRow = {
  page_id: string;
  page_name: string;
  instagram_account_id?: string;
  posts_per_day?: number;
  posting_times?: string;
  language?: string;
  status?: string;
};

export function ChannelsPage({ boot, translator, loading, error, payload, refresh }: ChannelsProps) {
  const { push } = useToast();
  const channels = (payload?.channels || {}) as Record<string, unknown>;
  const pagesPayload = (channels.pages || {}) as { pages?: PageRow[] };
  const pages = Array.isArray(pagesPayload.pages) ? pagesPayload.pages : [];
  const facebook = (channels.facebook || {}) as Record<string, unknown>;
  const instagram = (channels.instagram || {}) as Record<string, unknown>;
  const telegramCode = (channels.telegram_code || {}) as Record<string, unknown>;
  const telegramStatus = (channels.telegram_status || {}) as Record<string, unknown>;
  const telegramSummary = (channels.telegram_summary || {}) as Record<string, unknown>;
  const active = useMemo(() => pages.find((page) => page.status === "active") || pages[0] || null, [pages]);

  const [pageName, setPageName] = useState("");
  const [pageLanguage, setPageLanguage] = useState("en");
  const [postsPerDay, setPostsPerDay] = useState("3");
  const [postingTimes, setPostingTimes] = useState("");
  const [summaryEnabled, setSummaryEnabled] = useState(false);
  const [summaryTime, setSummaryTime] = useState("08:00");

  useEffect(() => {
    setPageName(active?.page_name || "");
    setPageLanguage(String(active?.language || "en").toLowerCase());
    setPostsPerDay(String(active?.posts_per_day || 3));
    setPostingTimes(String(active?.posting_times || ""));
  }, [active]);

  useEffect(() => {
    setSummaryEnabled(Boolean(telegramSummary.enabled));
    setSummaryTime(String(telegramSummary.daily_summary_time || "08:00"));
  }, [telegramSummary.daily_summary_time, telegramSummary.enabled]);

  const reload = async () => {
    await refresh(true);
  };

  const setActivePage = async (pageId: string) => {
    try {
      await apiCall(`/api/pages/${pageId}`, "PUT", { status: "active" });
      await reload();
      push(translator.tr("Active destination updated."));
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not update the active destination."), "error");
    }
  };

  const saveDefaults = async () => {
    if (!active) return;
    try {
      await apiCall(`/api/pages/${active.page_id}`, "PUT", {
        page_name: pageName,
        language: pageLanguage,
        posts_per_day: Number(postsPerDay || "3"),
        posting_times: postingTimes,
      });
      await reload();
      push(translator.tr("Destination defaults saved."));
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not save destination defaults."), "error");
    }
  };

  const disconnect = async () => {
    try {
      await apiCall("/api/facebook/disconnect", "POST", {});
      await reload();
      push(translator.tr("Facebook pages disconnected."));
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not disconnect Facebook."), "error");
    }
  };

  const saveTelegram = async () => {
    try {
      await apiCall("/api/telegram/summary-settings", "POST", {
        enabled: summaryEnabled,
        daily_summary_time: summaryTime,
      });
      push(translator.tr("Telegram summary settings saved."));
      await reload();
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not save Telegram settings."), "error");
    }
  };

  const togglePause = async (paused: boolean) => {
    try {
      await apiCall("/api/telegram/pause", "POST", { paused });
      push(translator.tr(paused ? "Automation paused for this account." : "Automation resumed for this account."));
      await reload();
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr(paused ? "Could not pause automation." : "Could not resume automation."), "error");
    }
  };

  return (
    <section className="cf-screen">
      <header className="cf-page-intro">
        <div>
          <h1 className="cf-page-title">{translator.tr("Channels")}</h1>
          <p className="cf-page-copy">{translator.tr("Connection and destination control")}</p>
        </div>
      </header>

      {error && !payload ? (
        <article className="cf-card cf-panel">
          <ErrorState title={translator.tr("Something failed to load")} copy={translator.maybeTr(error)} />
        </article>
      ) : null}

      <section className="cf-grid cols-2">
        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Destinations")}</span>
          </div>
          {!pages.length ? (
            <EmptyState
              title={translator.tr("No destinations connected")}
              copy={translator.tr("Use Facebook OAuth to add the first publishing destination.")}
              action={<a className="cf-btn" href="/oauth/facebook">{translator.tr("Connect Facebook")}</a>}
            />
          ) : (
            <div className="cf-pages">
              {pages.map((page) => (
                <article key={page.page_id} className={`cf-card cf-page-card ${page.page_id === active?.page_id ? "ok" : "warn"}`}>
                  <div className="cf-page-platforms">{translator.maybeTr(page.instagram_account_id ? "Facebook + Instagram" : "Facebook")}</div>
                  <div className="cf-page-reach">{page.page_name}</div>
                  <div className="cf-row-sub">{translator.tr("Page ID: {page_id}", { page_id: page.page_id })}</div>
                  <div className="cf-inline-actions">
                    <span className={`cf-pill ${page.page_id === active?.page_id ? "is-active" : ""}`}>{translator.maybeTr(page.page_id === active?.page_id ? "Active" : (page.status || "Inactive"))}</span>
                    <button type="button" className="cf-btn-ghost" onClick={() => void setActivePage(page.page_id)}>{translator.tr("Set active")}</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </article>

        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Active destination")}</span>
          </div>
          {active ? (
            <>
              <div className="cf-health-grid">
                <article className="cf-health-cell">
                  <div className="cf-health-label">{translator.tr("Destination")}</div>
                  <div className="cf-health-value">{active.page_name}</div>
                  <div className="cf-inline-note">{active.page_id}</div>
                </article>
                <article className="cf-health-cell">
                  <div className="cf-health-label">{translator.tr("Facebook")}</div>
                  <div className="cf-health-value">{translator.maybeTr(Boolean(facebook.connected) ? "Connected" : "Disconnected")}</div>
                  <div className="cf-inline-note">{translator.maybeTr(String(facebook.reason || "Connected"))}</div>
                </article>
                <article className="cf-health-cell">
                  <div className="cf-health-label">{translator.tr("Instagram")}</div>
                  <div className="cf-health-value">{translator.maybeTr(Boolean(instagram.connected) ? "Linked" : "Not linked")}</div>
                  <div className="cf-inline-note">{translator.maybeTr(Boolean(instagram.connected) ? "Connected" : "Missing")}</div>
                </article>
                <article className="cf-health-cell">
                  <div className="cf-health-label">{translator.tr("Language")}</div>
                  <div className="cf-health-value">{String(active.language || "en").toUpperCase()}</div>
                  <div className="cf-inline-note">{translator.tr("Connected through the Channels flow")}</div>
                </article>
              </div>
              <div className="cf-inline-actions">
                <a className="cf-btn" href="/oauth/facebook">{translator.tr("Reconnect Facebook")}</a>
                <button type="button" className="cf-btn-ghost" onClick={() => void disconnect()}>{translator.tr("Disconnect current pages")}</button>
              </div>
            </>
          ) : (
            <EmptyState title={translator.tr("No active destination")} copy={translator.tr("Choose a page after the Facebook OAuth flow completes.")} />
          )}
        </article>
      </section>

      <section className="cf-grid cols-2">
        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Destination defaults")}</span>
          </div>
          {active ? (
            <>
              <div className="cf-settings-grid">
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-react-page-name">{translator.tr("Page name")}</label>
                  <input id="cf-react-page-name" className="cf-input" value={pageName} onChange={(event) => setPageName(event.target.value)} />
                </div>
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-react-page-language">{translator.tr("Language")}</label>
                  <select id="cf-react-page-language" className="cf-select" value={pageLanguage} onChange={(event) => setPageLanguage(event.target.value)}>
                    <option value="en">{translator.tr("English")}</option>
                    <option value="fr">{translator.tr("French")}</option>
                    <option value="ar">{translator.tr("Arabic")}</option>
                  </select>
                </div>
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-react-posts-per-day">{translator.tr("Posts per day")}</label>
                  <input id="cf-react-posts-per-day" className="cf-input" type="number" min="1" max="12" value={postsPerDay} onChange={(event) => setPostsPerDay(event.target.value)} />
                </div>
                <div className="cf-field cf-field-span">
                  <label className="cf-field-label" htmlFor="cf-react-posting-times">{translator.tr("Posting times")}</label>
                  <input id="cf-react-posting-times" className="cf-input" value={postingTimes} onChange={(event) => setPostingTimes(event.target.value)} />
                </div>
              </div>
              <div className="cf-inline-actions">
                <button type="button" className="cf-btn" onClick={() => void saveDefaults()}>{translator.tr("Save destination defaults")}</button>
                <span className="cf-inline-note">{translator.tr("{count} destination(s) loaded in this workspace.", { count: pages.length })}</span>
              </div>
            </>
          ) : (
            <EmptyState title={translator.tr("No defaults available")} copy={translator.tr("Connect a page before editing publishing defaults.")} />
          )}
        </article>

        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Telegram")}</span>
          </div>
          <div className="cf-grid cols-2">
            <article className="cf-note-block">
              <div className="cf-label">{translator.tr("Connect bot")}</div>
              <div className="cf-empty-title">{translator.tr(Boolean(telegramStatus.connected) ? "Telegram connected" : "Telegram not connected")}</div>
              <div className="cf-empty-copy">{translator.tr("Use the deep link or activation code below to connect the bot to this account.")}</div>
              <div className="cf-health-value">{String(telegramCode.code || translator.tr("Unavailable"))}</div>
              <a className="cf-inline-link" href={String(telegramCode.deep_link || "#")} target="_blank" rel="noreferrer">{translator.tr("Open Telegram bot")}</a>
            </article>
            <article className="cf-note-block">
              <div className="cf-label">{translator.tr("Delivery settings")}</div>
              <label className="cf-toggle-card">
                <input type="checkbox" checked={summaryEnabled} onChange={(event) => setSummaryEnabled(event.target.checked)} />
                <span>
                  <strong>{translator.tr("Daily summary")}</strong>
                  <small>{translator.tr("Send a daily workflow summary to Telegram.")}</small>
                </span>
              </label>
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-react-summary-time">{translator.tr("Daily summary time")}</label>
                <input id="cf-react-summary-time" className="cf-input" type="time" value={summaryTime} onChange={(event) => setSummaryTime(event.target.value)} />
              </div>
              <div className="cf-inline-actions">
                <button type="button" className="cf-btn" onClick={() => void saveTelegram()}>{translator.tr("Save Telegram settings")}</button>
                <button type="button" className="cf-btn-ghost" onClick={() => void togglePause(true)}>{translator.tr("Pause automation")}</button>
                <button type="button" className="cf-btn-ghost" onClick={() => void togglePause(false)}>{translator.tr("Resume automation")}</button>
              </div>
            </article>
          </div>
        </article>
      </section>

      {loading && !payload ? (
        <article className="cf-card cf-panel">
          <div className="cf-inline-note">{translator.tr("Loading account state.")}</div>
        </article>
      ) : null}
    </section>
  );
}
