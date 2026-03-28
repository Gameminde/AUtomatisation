import { useEffect, useMemo, useState } from "react";

import { apiCall, BootstrapResponse } from "../lib/api";
import { BootPayload } from "../lib/boot";
import { Translator } from "../lib/i18n";
import { EmptyState, ErrorState } from "../ui/States";

type DashboardProps = {
  boot: BootPayload;
  translator: Translator;
  loading: boolean;
  error: string | null;
  payload: BootstrapResponse | null;
  refresh: (force?: boolean) => Promise<BootstrapResponse | null>;
};

type HealthEvent = {
  type?: string;
  message?: string;
  at?: string;
};

function StatusCard({ label, value, copy }: { label: string; value: string | number; copy: string }) {
  const valueText = String(value ?? "");
  const metricLike = /^[-+]?[\d\s.,/%]+$/.test(valueText);
  return (
    <article className="cf-card cf-stat-card">
      <div className="cf-label">{label}</div>
      <span className={`cf-stat-value ${metricLike ? "is-metric" : "is-copy"}`}>{valueText}</span>
      <div className="cf-stat-delta">{copy}</div>
    </article>
  );
}

function ApprovalCard({
  title,
  time,
  body,
  actionHref,
  actionLabel,
}: {
  title: string;
  time: string;
  body: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <article className="cf-approval-card">
      <div className="cf-approval-head">
        <div className="cf-approval-page">{title}</div>
        <span className="cf-platform-tag">{time}</span>
      </div>
      <div className="cf-approval-body">{body}</div>
      {actionHref && actionLabel ? (
        <div className="cf-approval-actions">
          <a className={actionLabel.toLowerCase().includes("review") ? "cf-btn" : "cf-btn-ghost"} href={actionHref}>
            {actionLabel}
          </a>
        </div>
      ) : null}
    </article>
  );
}

function Timeline({ events, translator }: { events: HealthEvent[]; translator: Translator }) {
  if (!events.length) {
    return <EmptyState title={translator.tr("No events yet")} copy={translator.tr("No recent system activity yet.")} />;
  }

  return (
    <>
      {events.map((event, index) => (
        <article className="cf-timeline-item" key={`${event.type || "event"}-${event.at || index}`}>
          <div className="cf-row-main">
            <strong>{translator.maybeTr(event.message || event.type || "Event")}</strong>
            <span className="cf-pill">{translator.maybeTr(event.type || "event")}</span>
          </div>
          <div className="cf-inline-note">{translator.dateTime(event.at)}</div>
        </article>
      ))}
    </>
  );
}

function DashboardList({
  items,
  emptyTitle,
  emptyCopy,
  renderItem,
}: {
  items: unknown[];
  emptyTitle: string;
  emptyCopy: string;
  renderItem: (item: Record<string, unknown>) => JSX.Element;
}) {
  if (!items.length) {
    return <EmptyState title={emptyTitle} copy={emptyCopy} />;
  }
  return <>{items.map((item, index) => renderItem({ ...(item as Record<string, unknown>), __index: index }))}</>;
}

export function DashboardPage({ boot, translator, loading, error, payload }: DashboardProps) {
  const dashboard = (payload?.dashboard || {}) as Record<string, unknown>;
  const shell = (payload?.shell || {}) as Record<string, unknown>;
  const summary = (dashboard.summary || {}) as Record<string, unknown>;
  const health = (dashboard.health || {}) as Record<string, unknown>;
  const pagesPayload = (dashboard.pages || {}) as Record<string, unknown>;
  const setup = (shell.setup || {}) as Record<string, unknown>;
  const status = (shell.status || {}) as Record<string, unknown>;
  const [events, setEvents] = useState<HealthEvent[]>(Array.isArray(dashboard.events) ? (dashboard.events as HealthEvent[]) : []);

  useEffect(() => {
    setEvents(Array.isArray(dashboard.events) ? (dashboard.events as HealthEvent[]) : []);
  }, [dashboard.events]);

  useEffect(() => {
    let active = true;
    apiCall<{ success: boolean; events?: HealthEvent[] }>("/api/health/events")
      .then((response) => {
        if (active && Array.isArray(response.events)) {
          setEvents(response.events);
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const pageRows = Array.isArray(pagesPayload.pages) ? (pagesPayload.pages as Array<Record<string, unknown>>) : [];
  const pipeline = (health.pipeline || {}) as Record<string, unknown>;
  const rateLimiter = (status.rate_limiter || {}) as Record<string, unknown>;
  const lastError = (health.last_error || {}) as Record<string, unknown>;
  const requiredSteps = Array.isArray(setup.steps) ? (setup.steps as Array<Record<string, unknown>>).filter((step) => !step.optional) : [];
  const completedRequired = requiredSteps.filter((step) => Boolean(step.completed)).length;
  const nextStep = requiredSteps.find((step) => String(step.id || "") === String(setup.next_required_step || ""));
  const setupPercent = requiredSteps.length ? Math.round((completedRequired / requiredSteps.length) * 100) : 100;

  const attentionCards = useMemo(
    () => [
      {
        label: translator.tr("Pending approvals"),
        value: Number(pipeline.pending_approvals || 0),
        copy: translator.tr("Needs review before publishing."),
      },
      {
        label: translator.tr("Queue size"),
        value: Number(pipeline.queue_size || 0),
        copy: translator.tr("Scheduled items waiting to publish."),
      },
      {
        label: translator.tr("Failed items"),
        value: Number(pipeline.failed_count || 0),
        copy: translator.maybeTr(String(lastError.message || "No recent publish failure.")),
      },
      {
        label: translator.tr("Remaining today"),
        value: Number(rateLimiter.remaining ?? 0),
        copy: translator.tr("{used}/{limit} posts used today.", {
          used: Number(rateLimiter.posts_today || 0),
          limit: Number(rateLimiter.daily_limit || 0),
        }),
      },
    ],
    [lastError.message, pipeline.failed_count, pipeline.pending_approvals, pipeline.queue_size, rateLimiter.daily_limit, rateLimiter.posts_today, rateLimiter.remaining, translator],
  );

  return (
    <section className="cf-screen cf-dashboard-page" data-cf-dashboard="">
      <header className="cf-page-intro cf-page-intro-actions">
        <div>
          <h1 className="cf-page-title">{translator.tr("Daily operations cockpit")}</h1>
          <p className="cf-page-copy">{translator.tr("See what needs action now, what is scheduled next, and whether the pipeline is safe to trust today.")}</p>
        </div>
      </header>

      <section className="cf-dashboard-shell">
        <div className="cf-dashboard-main">
          <div id="cf-dashboard-setup" className="cf-dashboard-setup-slot" aria-live="polite">
            {!setup.all_required_complete && nextStep ? (
              <article className="cf-card cf-dashboard-banner">
                <div className="cf-dashboard-banner-body">
                  <div className="cf-dashboard-banner-copy">
                    <div className="cf-label">{translator.tr("Setup")}</div>
                    <div className="cf-dashboard-banner-title">{translator.maybeTr(String(nextStep.label || "Finish required setup"))}</div>
                    <div className="cf-dashboard-banner-desc">{translator.maybeTr(String(nextStep.description || "Complete the required setup to publish."))}</div>
                  </div>
                  <div className="cf-dashboard-banner-actions">
                    <a className="cf-btn" href={String(nextStep.action_url || boot.urls.settings)}>
                      {translator.maybeTr(String(nextStep.action_label || "Open setup"))}
                    </a>
                  </div>
                </div>
                <div className="cf-dashboard-banner-progress">
                  <div className="cf-dashboard-banner-fill" style={{ width: `${setupPercent}%` }} />
                </div>
              </article>
            ) : null}
          </div>

          <article className="cf-card cf-panel cf-dashboard-priority">
            <div className="cf-section-head cf-section-head-quiet">
              <span className="cf-label">{translator.tr("Attention")}</span>
            </div>
            <div id="cf-dashboard-attention" className="cf-grid cols-4" aria-live="polite">
              {attentionCards.map((card) => (
                <StatusCard key={card.label} label={card.label} value={card.value} copy={card.copy} />
              ))}
            </div>
          </article>

          <section className="cf-grid cols-2 cf-dashboard-flow">
            <article className="cf-card cf-panel">
              <div className="cf-section-head cf-section-head-quiet">
                <span className="cf-label">{translator.tr("Upcoming")}</span>
              </div>
              <div id="cf-dashboard-upcoming" aria-live="polite">
                <DashboardList
                  items={Array.isArray(summary.scheduled) ? (summary.scheduled as unknown[]) : []}
                  emptyTitle={translator.tr("Nothing to show")}
                  emptyCopy={translator.tr("No scheduled posts.")}
                  renderItem={(item) => (
                    <ApprovalCard
                      key={`scheduled-${String(item.id || item.__index)}`}
                      title={translator.tr("Scheduled post")}
                      time={translator.maybeTr(String(item.time || "Pending"))}
                      body={String(item.text || translator.tr("Scheduled content"))}
                      actionHref={boot.urls.studio}
                      actionLabel={translator.tr("Open in Studio")}
                    />
                  )}
                />
              </div>
            </article>

            <article className="cf-card cf-panel">
              <div className="cf-section-head cf-section-head-quiet">
                <span className="cf-label">{translator.tr("Needs review")}</span>
              </div>
              <div id="cf-dashboard-review" aria-live="polite">
                <DashboardList
                  items={Array.isArray(summary.pending) ? (summary.pending as unknown[]) : []}
                  emptyTitle={translator.tr("Nothing to show")}
                  emptyCopy={translator.tr("No items are waiting for review.")}
                  renderItem={(item) => (
                    <ApprovalCard
                      key={`review-${String(item.id || item.__index)}`}
                      title={translator.tr("Needs review")}
                      time={translator.maybeTr(String(item.time || "Now"))}
                      body={String(item.text || translator.tr("Draft awaiting review"))}
                      actionHref={boot.urls.studio}
                      actionLabel={translator.tr("Review in Studio")}
                    />
                  )}
                />
              </div>
            </article>
          </section>

          <article className="cf-card cf-panel">
            <div className="cf-section-head cf-section-head-quiet">
              <span className="cf-label">{translator.tr("Recent output")}</span>
            </div>
            <div id="cf-dashboard-recent-output" aria-live="polite">
              <DashboardList
                items={Array.isArray(summary.published) ? (summary.published as unknown[]) : []}
                emptyTitle={translator.tr("Nothing to show")}
                emptyCopy={translator.tr("Nothing has been published yet.")}
                renderItem={(item) => (
                  <ApprovalCard
                    key={`published-${String(item.id || item.__index)}`}
                    title={translator.tr("Published")}
                    time={translator.maybeTr(String(item.time || "Recently"))}
                    body={String(item.text || translator.tr("Published content"))}
                  />
                )}
              />
            </div>
          </article>
        </div>

        <aside className="cf-dashboard-side">
          <article className="cf-card cf-panel cf-dashboard-side-card">
            <div className="cf-section-head cf-section-head-quiet">
              <span className="cf-label">{translator.tr("Performance snapshot")}</span>
            </div>
            <div id="cf-dashboard-performance" className="cf-grid cols-3" aria-live="polite">
              <StatusCard label={translator.tr("Published 7d")} value={Number(pipeline.published_count_7d || 0)} copy={translator.tr("Recent publishing volume.")} />
              <StatusCard label={translator.tr("Last publish")} value={pipeline.last_published_at ? translator.date(String(pipeline.last_published_at)) : translator.tr("Never")} copy={translator.maybeTr(String((health.cooldown as Record<string, unknown> | undefined)?.reason || "No cooldown active."))} />
              <StatusCard label={translator.tr("Account health")} value={translator.maybeTr(String(status.health || "Unknown"))} copy={translator.maybeTr(String(status.post_reason || "No current status message."))} />
            </div>
          </article>

          <article className="cf-card cf-panel cf-dashboard-side-card">
            <div className="cf-section-head cf-section-head-quiet">
              <span className="cf-label">{translator.tr("Destination snapshot")}</span>
            </div>
            <div id="cf-dashboard-destination" aria-live="polite">
              {pageRows.length ? (
                <>
                  {pageRows.map((pageRow) => (
                    <article
                      key={String(pageRow.page_id || pageRow.page_name)}
                      className={`cf-card cf-page-card ${String(pageRow.status || "").toLowerCase() === "active" ? "ok" : "warn"}`}
                    >
                      <div className="cf-page-platforms">
                        {translator.maybeTr(pageRow.instagram_account_id ? "Facebook + Instagram" : "Facebook")}
                      </div>
                      <div className="cf-page-reach">{String(pageRow.page_name || translator.tr("Connected page"))}</div>
                      <div className="cf-row-sub">
                        {translator.tr("Page ID: {page_id}", { page_id: String(pageRow.page_id || translator.tr("Unknown")) })}
                      </div>
                      <div className="cf-row-main">
                        <span>{translator.tr("Connection")}</span>
                        <span className={`cf-status ${String(pageRow.status || "").toLowerCase() === "active" ? "ok" : "warn"}`}>
                          <span className="cf-status-dot" />
                          <span>{translator.maybeTr(String(pageRow.status || "Inactive"))}</span>
                        </span>
                      </div>
                    </article>
                  ))}
                </>
              ) : (
                <EmptyState
                  title={translator.tr("No connected destination")}
                  copy={translator.tr("Connect Facebook from Channels to start publishing.")}
                  action={<a className="cf-btn" href={boot.urls.channels}>{translator.tr("Open Channels")}</a>}
                />
              )}
            </div>
          </article>

          <article className="cf-card cf-panel cf-dashboard-side-card">
            <div className="cf-section-head cf-section-head-quiet">
              <span className="cf-label">{translator.tr("Recent activity")}</span>
            </div>
            <div id="cf-dashboard-activity" className="cf-timeline" aria-live="polite">
              {error && !events.length ? (
                <ErrorState title={translator.tr("Something failed to load")} copy={translator.maybeTr(error)} />
              ) : (
                <Timeline events={events} translator={translator} />
              )}
            </div>
          </article>
        </aside>
      </section>

      {error && !loading && !payload ? (
        <article className="cf-card cf-panel">
          <ErrorState title={translator.tr("Something failed to load")} copy={translator.maybeTr(error)} />
        </article>
      ) : null}
    </section>
  );
}
