export async function initDiagnostics(ctx) {
  try {
    const bootstrap = await ctx.loadBootstrap();
    const diagnostics = bootstrap.diagnostics || {};
    const health = diagnostics.health || {};
    const events = { events: diagnostics.events || [] };
    const pipeline = health.pipeline || {};

    ctx.$("#cf-diagnostics-summary").innerHTML = [
      ctx.card("Page", health.page?.connected ? "Connected" : "Missing", health.page?.page_name || "No active Facebook page."),
      ctx.card("Cooldown", health.cooldown?.active ? "Active" : "Ready", health.cooldown?.reason || "Publishing is ready."),
      ctx.card("Pending", pipeline.pending_approvals || 0, "Items waiting for manual review."),
      ctx.card("Failures", pipeline.failed_count || 0, (health.last_error || {}).message || "No recent publish failure."),
    ].join("");

    ctx.$("#cf-diagnostics-failures").innerHTML = health.last_error
      ? `<article class="cf-note-block"><div class="cf-label">${ctx.tt("Latest error")}</div><div class="cf-empty-title">${ctx.esc(ctx.maybeTr(health.last_error.status || "failed"))}</div><div class="cf-empty-copy">${ctx.esc(ctx.maybeTr(health.last_error.message || health.last_error.code || "Unknown error"))}</div><div class="cf-inline-note">${ctx.tt("Recorded")} ${ctx.esc(ctx.dateTime(health.last_error.at))}</div><div class="cf-inline-note">${ctx.tt("Retry count:")} ${ctx.esc(health.last_error.retry_count || 0)}</div><div class="cf-inline-note">${ctx.tt("Next retry:")} ${ctx.esc(ctx.dateTime(health.last_error.next_retry_at))}</div></article>`
      : ctx.empty("No open failures", "The pipeline has not recorded a recent error.");

    const tokens = health.tokens || {};
    ctx.$("#cf-diagnostics-destinations").innerHTML = `<div class="cf-health-grid"><article class="cf-health-cell"><div class="cf-health-label">${ctx.tt("Facebook")}</div><div class="cf-health-value">${ctx.esc(tokens.facebook_page_name || health.page?.page_name || ctx.tr("Not connected"))}</div>${ctx.line("Token", tokens.facebook_status || "missing")}</article><article class="cf-health-cell"><div class="cf-health-label">${ctx.tt("Instagram")}</div><div class="cf-health-value">${ctx.esc(tokens.instagram_connected ? ctx.tr("Connected") : ctx.tr("Not connected"))}</div>${ctx.line("State", tokens.instagram_connected ? "Connected" : "Missing", tokens.instagram_connected ? "ok" : "warn")}</article><article class="cf-health-cell"><div class="cf-health-label">AI</div><div class="cf-health-value">${ctx.esc(tokens.ai ? ctx.tr("Ready") : ctx.tr("Missing key"))}</div>${ctx.line("Source", tokens.ai_source || "unknown", tokens.ai ? "ok" : "warn")}</article><article class="cf-health-cell"><div class="cf-health-label">${ctx.tt("Images")}</div><div class="cf-health-value">${ctx.esc(tokens.pexels ? ctx.tr("Ready") : ctx.tr("Optional"))}</div>${ctx.line("Pexels", tokens.pexels ? "Configured" : "Not set", tokens.pexels ? "ok" : "warn")}</article></div>`;

    ctx.$("#cf-diagnostics-checks").innerHTML = ["facebook", "ai", "pexels", "database"].map((service) => `<button type="button" class="cf-service-test" data-health-test="${service}"><div class="cf-format-name">${ctx.esc(ctx.tr("Test {service}", { service }))}</div><div class="cf-format-copy" id="cf-health-result-${service}">${ctx.tt("Run a live check against the current workspace state.")}</div></button>`).join("");
    document.querySelectorAll("[data-health-test]").forEach((button) => button.addEventListener("click", async () => {
      const service = button.dataset.healthTest;
      const output = ctx.$(`#cf-health-result-${service}`);
      if (output) output.textContent = ctx.tr("Testing...");
      try {
        const response = await ctx.apiCall(`/api/health/test/${service}`);
        if (output) output.textContent = ctx.maybeTr(response.message || "Service check passed.");
      } catch (error) {
        if (output) output.textContent = ctx.maybeTr(error.message || "Service check failed.");
      }
    }));

    ctx.timeline("#cf-diagnostics-events", events.events || [], "No diagnostic events recorded yet.");
  } catch (error) {
    ["#cf-diagnostics-summary", "#cf-diagnostics-failures", "#cf-diagnostics-destinations", "#cf-diagnostics-checks", "#cf-diagnostics-events"].forEach((selector) => {
      if (ctx.$(selector)) ctx.$(selector).innerHTML = ctx.fail(error.message || "Could not load diagnostics.");
    });
  }
}
