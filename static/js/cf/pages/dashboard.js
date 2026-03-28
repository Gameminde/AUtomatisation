export async function initDashboard(ctx) {
  try {
    const bootstrap = await ctx.loadBootstrap();
    const dashboard = bootstrap.dashboard || {};
    const setup = (bootstrap.shell || {}).setup || {};
    const status = (bootstrap.shell || {}).status || {};
    const summary = dashboard.summary || {};
    const health = dashboard.health || {};
    const events = { events: dashboard.events || [] };
    const pages = dashboard.pages || { pages: [] };

    if (!setup.all_required_complete && ctx.$("#cf-dashboard-setup")) {
      const requiredSteps = (setup.steps || []).filter((step) => !step.optional);
      const completed = requiredSteps.filter((step) => step.completed).length;
      const next = (setup.steps || []).find((step) => step.id === setup.next_required_step);
      const percent = requiredSteps.length ? Math.round((completed / requiredSteps.length) * 100) : 0;
      ctx.$("#cf-dashboard-setup").innerHTML = `<article class="cf-card cf-dashboard-banner"><div class="cf-dashboard-banner-body"><div class="cf-dashboard-banner-copy"><div class="cf-label">${ctx.tt("Setup")}</div><div class="cf-dashboard-banner-title">${ctx.esc(ctx.maybeTr(next?.label || "Finish required setup"))}</div><div class="cf-dashboard-banner-desc">${ctx.esc(ctx.maybeTr(next?.description || "Complete the required setup to publish."))}</div></div><div class="cf-dashboard-banner-actions"><a class="cf-btn" href="${ctx.esc(next?.action_url || "/settings")}">${ctx.tt(next?.action_label || "Open setup")}</a></div></div><div class="cf-dashboard-banner-progress"><div class="cf-dashboard-banner-fill" style="width:${percent}%"></div></div></article>`;
    }

    const pipeline = health.pipeline || {};
    const rateLimiter = status.rate_limiter || {};
    const usedToday = rateLimiter.posts_today || 0;
    const dailyLimit = rateLimiter.daily_limit || 0;
    ctx.$("#cf-dashboard-attention").innerHTML = [
      ctx.card("Pending approvals", pipeline.pending_approvals || 0, "Needs review before publishing."),
      ctx.card("Queue size", pipeline.queue_size || 0, "Scheduled items waiting to publish."),
      ctx.card("Failed items", pipeline.failed_count || 0, (health.last_error || {}).message || "No recent publish failure."),
      ctx.card("Remaining today", rateLimiter.remaining ?? 0, ctx.tt("{used}/{limit} posts used today.", { used: usedToday, limit: dailyLimit })),
    ].join("");

    ctx.blockList("#cf-dashboard-upcoming", summary.scheduled || [], "No scheduled posts.", (item) => `<article class="cf-approval-card"><div class="cf-approval-head"><div class="cf-approval-page">${ctx.tt("Scheduled post")}</div><span class="cf-platform-tag">${ctx.esc(ctx.maybeTr(item.time || "Pending"))}</span></div><div class="cf-approval-body">${ctx.esc(item.text || ctx.tr("Scheduled content"))}</div><div class="cf-approval-actions"><a class="cf-btn-ghost" href="/studio">${ctx.tt("Open in Studio")}</a></div></article>`);
    ctx.blockList("#cf-dashboard-review", summary.pending || [], "No items are waiting for review.", (item) => `<article class="cf-approval-card"><div class="cf-approval-head"><div class="cf-approval-page">${ctx.tt("Needs review")}</div><span class="cf-platform-tag">${ctx.esc(ctx.maybeTr(item.time || "Now"))}</span></div><div class="cf-approval-body">${ctx.esc(item.text || ctx.tr("Draft awaiting review"))}</div><div class="cf-approval-actions"><a class="cf-btn" href="/studio">${ctx.tt("Review in Studio")}</a></div></article>`);
    ctx.blockList("#cf-dashboard-recent-output", summary.published || [], "Nothing has been published yet.", (item) => `<article class="cf-approval-card"><div class="cf-approval-head"><div class="cf-approval-page">${ctx.tt("Published")}</div><span class="cf-platform-tag">${ctx.esc(ctx.maybeTr(item.time || "Recently"))}</span></div><div class="cf-approval-body">${ctx.esc(item.text || ctx.tr("Published content"))}</div></article>`);

    ctx.$("#cf-dashboard-performance").innerHTML = [
      ctx.card("Published 7d", pipeline.published_count_7d || 0, "Recent publishing volume."),
      ctx.card("Last publish", pipeline.last_published_at ? ctx.shortDate(pipeline.last_published_at) : "Never", health.cooldown?.reason || "No cooldown active."),
      ctx.card("Account health", status.health ? ctx.maybeTr(status.health) : ctx.tr("Unknown"), status.post_reason || "No current status message."),
    ].join("");

    const destinationPages = pages.pages || [];
    ctx.$("#cf-dashboard-destination").innerHTML = destinationPages.length
      ? destinationPages.map((pageRow) => `<article class="cf-card cf-page-card ${pageRow.status === "active" ? "ok" : "warn"}"><div class="cf-page-platforms">${ctx.esc(ctx.maybeTr(pageRow.instagram_account_id ? "Facebook + Instagram" : "Facebook"))}</div><div class="cf-page-reach">${ctx.esc(pageRow.page_name || ctx.tr("Connected page"))}</div><div class="cf-row-sub">${ctx.tt("Page ID: {page_id}", { page_id: pageRow.page_id || ctx.tr("Unknown") })}</div>${ctx.line("Connection", pageRow.status === "active" ? "Active" : (pageRow.status || "Inactive"), pageRow.status === "active" ? "ok" : "warn")}</article>`).join("")
      : ctx.empty("No connected destination", "Connect Facebook from Channels to start publishing.", "/channels", "Open Channels");

    if (ctx.$("#cf-dashboard-active-destination")) {
      ctx.$("#cf-dashboard-active-destination").textContent = (health.page || {}).page_name || destinationPages[0]?.page_name || ctx.tr("No destination");
    }
    ctx.timeline("#cf-dashboard-activity", events.events || [], "No recent system activity yet.");
    try {
      const activity = await ctx.apiCall("/api/health/events");
      ctx.timeline("#cf-dashboard-activity", activity.events || [], "No recent system activity yet.");
    } catch (_error) {
      // Keep the already-rendered dashboard visible; activity can fail independently.
    }
  } catch (error) {
    ["#cf-dashboard-attention", "#cf-dashboard-upcoming", "#cf-dashboard-review", "#cf-dashboard-recent-output", "#cf-dashboard-performance", "#cf-dashboard-destination", "#cf-dashboard-activity"].forEach((selector) => {
      if (ctx.$(selector)) ctx.$(selector).innerHTML = ctx.fail(error.message || "Could not load dashboard data.");
    });
  }
}
