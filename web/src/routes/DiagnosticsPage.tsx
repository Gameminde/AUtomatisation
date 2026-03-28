import { useMemo, useState } from "react";

import { apiCall, BootstrapResponse } from "../lib/api";
import { BootPayload } from "../lib/boot";
import { Translator } from "../lib/i18n";
import { EmptyState, ErrorState } from "../ui/States";
import { useToast } from "../ui/ToastProvider";

type DiagnosticsProps = {
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

export function DiagnosticsPage({ translator, loading, error, payload }: DiagnosticsProps) {
  const { push } = useToast();
  const diagnostics = (payload?.diagnostics || {}) as Record<string, unknown>;
  const health = (diagnostics.health || {}) as Record<string, unknown>;
  const pipeline = (health.pipeline || {}) as Record<string, unknown>;
  const tokens = (health.tokens || {}) as Record<string, unknown>;
  const lastError = (health.last_error || null) as Record<string, unknown> | null;
  const events = (Array.isArray(diagnostics.events) ? diagnostics.events : []) as HealthEvent[];
  const [checkResults, setCheckResults] = useState<Record<string, string>>({});

  const summaryCards = useMemo(
    () => [
      {
        label: translator.tr("Page"),
        value: translator.tr(Boolean((health.page as Record<string, unknown> | undefined)?.connected) ? "Connected" : "Missing"),
        copy: String((health.page as Record<string, unknown> | undefined)?.page_name || translator.tr("No active Facebook page.")),
      },
      {
        label: translator.tr("Cooldown"),
        value: translator.tr(Boolean((health.cooldown as Record<string, unknown> | undefined)?.active) ? "Active" : "Ready"),
        copy: String((health.cooldown as Record<string, unknown> | undefined)?.reason || translator.tr("Publishing is ready.")),
      },
      {
        label: translator.tr("Pending"),
        value: String(Number(pipeline.pending_approvals || 0)),
        copy: translator.tr("Items waiting for manual review."),
      },
      {
        label: translator.tr("Failures"),
        value: String(Number(pipeline.failed_count || 0)),
        copy: String((lastError || {}).message || translator.tr("No recent publish failure.")),
      },
    ],
    [health.cooldown, health.page, lastError, pipeline.failed_count, pipeline.pending_approvals, translator],
  );

  const runCheck = async (service: string) => {
    setCheckResults((current) => ({ ...current, [service]: translator.tr("Testing...") }));
    try {
      const response = await apiCall<{ message?: string }>(`/api/health/test/${service}`);
      setCheckResults((current) => ({ ...current, [service]: translator.maybeTr(response.message || "Service check passed.") }));
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : translator.tr("Service check failed.");
      setCheckResults((current) => ({ ...current, [service]: translator.maybeTr(message) }));
      push(message, "error");
    }
  };

  return (
    <section className="cf-screen">
      <header className="cf-page-intro">
        <div>
          <h1 className="cf-page-title">{translator.tr("Diagnostics")}</h1>
          <p className="cf-page-copy">{translator.tr("See what is broken, what is waiting to recover, and the fastest next action to restore the pipeline.")}</p>
        </div>
      </header>

      {error && !payload ? (
        <article className="cf-card cf-panel">
          <ErrorState title={translator.tr("Something failed to load")} copy={translator.maybeTr(error)} />
        </article>
      ) : null}

      <section className="cf-grid cols-4">
        {summaryCards.map((card) => (
          <article key={card.label} className="cf-card cf-stat-card">
            <div className="cf-label">{card.label}</div>
            <div className="cf-stat-value">{card.value}</div>
            <div className="cf-stat-delta">{card.copy}</div>
          </article>
        ))}
      </section>

      <section className="cf-grid cols-2">
        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Latest error")}</span>
          </div>
          {lastError ? (
            <article className="cf-note-block">
              <div className="cf-empty-title">{translator.maybeTr(String(lastError.status || "failed"))}</div>
              <div className="cf-empty-copy">{translator.maybeTr(String(lastError.message || lastError.code || "Unknown error"))}</div>
              <div className="cf-inline-note">{translator.tr("Recorded")} {translator.dateTime(String(lastError.at || ""))}</div>
              <div className="cf-inline-note">{translator.tr("Retry count:")} {String(lastError.retry_count || 0)}</div>
              <div className="cf-inline-note">{translator.tr("Next retry:")} {translator.dateTime(String(lastError.next_retry_at || ""))}</div>
            </article>
          ) : (
            <EmptyState title={translator.tr("No open failures")} copy={translator.tr("The pipeline has not recorded a recent error.")} />
          )}
        </article>

        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Destination health")}</span>
          </div>
          <div className="cf-health-grid">
            <article className="cf-health-cell">
              <div className="cf-health-label">{translator.tr("Facebook")}</div>
              <div className="cf-health-value">{String(tokens.facebook_page_name || (health.page as Record<string, unknown> | undefined)?.page_name || translator.tr("Not connected"))}</div>
              <div className="cf-inline-note">{translator.maybeTr(String(tokens.facebook_status || "missing"))}</div>
            </article>
            <article className="cf-health-cell">
              <div className="cf-health-label">{translator.tr("Instagram")}</div>
              <div className="cf-health-value">{translator.tr(Boolean(tokens.instagram_connected) ? "Connected" : "Not connected")}</div>
              <div className="cf-inline-note">{translator.tr(Boolean(tokens.instagram_connected) ? "Connected" : "Missing")}</div>
            </article>
            <article className="cf-health-cell">
              <div className="cf-health-label">AI</div>
              <div className="cf-health-value">{translator.tr(Boolean(tokens.ai) ? "Ready" : "Missing key")}</div>
              <div className="cf-inline-note">{translator.maybeTr(String(tokens.ai_source || "unknown"))}</div>
            </article>
            <article className="cf-health-cell">
              <div className="cf-health-label">{translator.tr("Images")}</div>
              <div className="cf-health-value">{translator.tr(Boolean(tokens.pexels) ? "Ready" : "Optional")}</div>
              <div className="cf-inline-note">{translator.tr(Boolean(tokens.pexels) ? "Configured" : "Not set")}</div>
            </article>
          </div>
        </article>
      </section>

      <section className="cf-grid cols-2">
        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Service checks")}</span>
          </div>
          <div className="cf-action-stack">
            {["facebook", "ai", "pexels", "database"].map((service) => (
              <button key={service} type="button" className="cf-service-test" onClick={() => void runCheck(service)}>
                <div className="cf-format-name">{translator.tr("Test {service}", { service })}</div>
                <div className="cf-format-copy">{checkResults[service] || translator.tr("Run a live check against the current workspace state.")}</div>
              </button>
            ))}
          </div>
        </article>

        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Event timeline")}</span>
          </div>
          <div className="cf-timeline">
            {events.length ? events.map((event, index) => (
              <article key={`${event.type || "event"}-${event.at || index}`} className="cf-timeline-item">
                <div className="cf-row-main">
                  <strong>{translator.maybeTr(event.message || event.type || "Event")}</strong>
                  <span className="cf-pill">{translator.maybeTr(event.type || "event")}</span>
                </div>
                <div className="cf-inline-note">{translator.dateTime(event.at)}</div>
              </article>
            )) : <EmptyState title={translator.tr("No events yet")} copy={translator.tr("No diagnostic events recorded yet.")} />}
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
