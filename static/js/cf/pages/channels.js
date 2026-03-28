export async function initChannels(ctx) {
  try {
    const bootstrap = await ctx.loadBootstrap();
    const channels = bootstrap.channels || {};
    const pagesPayload = channels.pages || { pages: [] };
    const facebook = channels.facebook || {};
    const instagram = channels.instagram || {};
    const telegramCode = channels.telegram_code || {};
    const telegramStatus = channels.telegram_status || {};
    const telegramSummary = channels.telegram_summary || {};
    const pages = pagesPayload.pages || [];
    const active = pages.find((pageRow) => pageRow.status === "active") || pages[0] || null;

    ctx.$("#cf-channels-destination-list").innerHTML = pages.length
      ? pages.map((pageRow) => `<article class="cf-card cf-page-card ${pageRow.page_id === active?.page_id ? "ok" : "warn"}"><div class="cf-page-platforms">${ctx.esc(ctx.maybeTr(pageRow.instagram_account_id ? "Facebook + Instagram" : "Facebook"))}</div><div class="cf-page-reach">${ctx.esc(pageRow.page_name || ctx.tr("Connected page"))}</div><div class="cf-row-sub">${ctx.tt("Page ID: {page_id}", { page_id: pageRow.page_id || ctx.tr("Unknown") })}</div><div class="cf-row-sub">${ctx.tt("Language")}: ${ctx.esc((pageRow.language || "en").toUpperCase())}</div><div class="cf-inline-actions"><span class="cf-pill ${pageRow.page_id === active?.page_id ? "is-active" : ""}">${ctx.esc(ctx.maybeTr(pageRow.page_id === active?.page_id ? "Active" : (pageRow.status || "inactive")))}</span><button type="button" class="cf-btn-ghost" data-set-active="${ctx.esc(pageRow.page_id)}">${ctx.tt("Set active")}</button></div></article>`).join("")
      : ctx.empty("No destinations connected", "Use Facebook OAuth to add the first publishing destination.", "/oauth/facebook", "Connect Facebook");

    document.querySelectorAll("[data-set-active]").forEach((button) => button.addEventListener("click", async () => {
      const pageId = button.dataset.setActive;
      try {
        await ctx.apiCall(`/api/pages/${pageId}`, "PUT", { status: "active" });
        await ctx.refreshBootstrap();
        ctx.toast("Active destination updated.");
        initChannels(ctx);
      } catch (error) {
        ctx.toast(error.message || "Could not update the active destination.", "error");
      }
    }));

    ctx.$("#cf-channels-connect-callout").innerHTML = facebook.connected && active
      ? ""
      : ctx.empty("Facebook is not connected", "The shell is ready, but publishing still needs an active Facebook page connection.", "/oauth/facebook", "Connect Facebook");

    ctx.$("#cf-channels-active-detail").innerHTML = active
      ? `<div class="cf-health-grid"><article class="cf-health-cell"><div class="cf-health-label">${ctx.tt("Destination")}</div><div class="cf-health-value">${ctx.esc(active.page_name || ctx.tr("Connected page"))}</div><div class="cf-inline-note">${ctx.esc(active.page_id || "")}</div></article><article class="cf-health-cell"><div class="cf-health-label">${ctx.tt("Facebook")}</div><div class="cf-health-value">${ctx.esc(ctx.maybeTr(facebook.connected ? "Connected" : "Disconnected"))}</div>${ctx.line("State", facebook.connected ? "Connected" : (facebook.reason || "Missing"), facebook.connected ? "ok" : "warn")}</article><article class="cf-health-cell"><div class="cf-health-label">${ctx.tt("Instagram")}</div><div class="cf-health-value">${ctx.esc(ctx.maybeTr(instagram.connected ? "Linked" : "Not linked"))}</div>${ctx.line("State", instagram.connected ? "Connected" : (instagram.reason || "Missing"), instagram.connected ? "ok" : "warn")}</article><article class="cf-health-cell"><div class="cf-health-label">${ctx.tt("Language")}</div><div class="cf-health-value">${ctx.esc((active.language || "en").toUpperCase())}</div><div class="cf-inline-note">${ctx.tt("Connected through the Channels flow")}</div></article></div><div class="cf-inline-actions"><a class="cf-btn" href="/oauth/facebook">${ctx.tt("Reconnect Facebook")}</a><button type="button" class="cf-btn-ghost" id="cf-channels-disconnect">${ctx.tt("Disconnect current pages")}</button></div>`
      : ctx.empty("No active destination", "Choose a page after the Facebook OAuth flow completes.");

    ctx.$("#cf-channels-disconnect")?.addEventListener("click", async () => {
      try {
        await ctx.apiCall("/api/facebook/disconnect", "POST", {});
        await ctx.refreshBootstrap();
        ctx.toast("Facebook pages disconnected.");
        initChannels(ctx);
      } catch (error) {
        ctx.toast(error.message || "Could not disconnect Facebook.", "error");
      }
    });

    ctx.$("#cf-channels-defaults").innerHTML = active
      ? `<div class="cf-settings-grid"><div class="cf-field"><label class="cf-field-label" for="cf-channels-page-name">${ctx.tt("Page name")}</label><input id="cf-channels-page-name" class="cf-input" type="text" value="${ctx.esc(active.page_name || "")}"></div><div class="cf-field"><label class="cf-field-label" for="cf-channels-language">${ctx.tt("Language")}</label><select id="cf-channels-language" class="cf-select"><option value="en" ${(active.language || "en") === "en" ? "selected" : ""}>${ctx.tt("English")}</option><option value="fr" ${(active.language || "en") === "fr" ? "selected" : ""}>${ctx.tt("French")}</option><option value="ar" ${(active.language || "en") === "ar" ? "selected" : ""}>${ctx.tt("Arabic")}</option></select></div><div class="cf-field"><label class="cf-field-label" for="cf-channels-posts-per-day">${ctx.tt("Posts per day")}</label><input id="cf-channels-posts-per-day" class="cf-input" type="number" min="1" max="12" value="${ctx.esc(active.posts_per_day || 3)}"></div><div class="cf-field cf-field-span"><label class="cf-field-label" for="cf-channels-posting-times">${ctx.tt("Posting times")}</label><input id="cf-channels-posting-times" class="cf-input" type="text" value="${ctx.esc(active.posting_times || "")}" placeholder="08:00,12:30,18:00"></div></div><div class="cf-inline-actions"><button type="button" class="cf-btn" id="cf-channels-save-defaults">${ctx.tt("Save destination defaults")}</button><span class="cf-inline-note">${ctx.esc(ctx.tr("{count} destination(s) loaded in this workspace.", { count: pages.length }))}</span></div>`
      : ctx.empty("No defaults available", "Connect a page before editing publishing defaults.");

    ctx.$("#cf-channels-save-defaults")?.addEventListener("click", async () => {
      try {
        await ctx.apiCall(`/api/pages/${active.page_id}`, "PUT", {
          page_name: ctx.$("#cf-channels-page-name")?.value || active.page_name,
          language: ctx.$("#cf-channels-language")?.value || active.language,
          posts_per_day: Number(ctx.$("#cf-channels-posts-per-day")?.value || active.posts_per_day || 3),
          posting_times: ctx.$("#cf-channels-posting-times")?.value || active.posting_times || "",
        });
        await ctx.refreshBootstrap();
        ctx.toast("Destination defaults saved.");
        initChannels(ctx);
      } catch (error) {
        ctx.toast(error.message || "Could not save destination defaults.", "error");
      }
    });

    ctx.$("#cf-channels-telegram").innerHTML = `<div class="cf-telegram-card"><article class="cf-note-block"><div class="cf-label">${ctx.tt("Connect bot")}</div><div class="cf-empty-title">${ctx.tt(telegramStatus.connected ? "Telegram connected" : "Telegram not connected")}</div><div class="cf-empty-copy">${ctx.tt("Use the deep link or activation code below to connect the bot to this account.")}</div><div class="cf-telegram-code">${ctx.esc(telegramCode.code || ctx.tr("Unavailable"))}</div><a class="cf-inline-link" href="${ctx.esc(telegramCode.deep_link || "#")}" target="_blank" rel="noreferrer">${ctx.tt("Open Telegram bot")}</a></article><article class="cf-note-block"><div class="cf-label">${ctx.tt("Delivery settings")}</div><label class="cf-toggle-card"><input id="cf-telegram-summary-enabled" type="checkbox" ${telegramSummary.enabled ? "checked" : ""}><span><strong>${ctx.tt("Daily summary")}</strong><small>${ctx.tt("Send a daily workflow summary to Telegram.")}</small></span></label><div class="cf-field"><label class="cf-field-label" for="cf-telegram-summary-time">${ctx.tt("Daily summary time")}</label><input id="cf-telegram-summary-time" class="cf-input" type="time" value="${ctx.esc(telegramSummary.daily_summary_time || "08:00")}"></div><div class="cf-inline-actions"><button type="button" class="cf-btn" id="cf-telegram-save-summary">${ctx.tt("Save Telegram settings")}</button><button type="button" class="cf-btn-ghost" id="cf-telegram-pause">${ctx.tt("Pause automation")}</button><button type="button" class="cf-btn-ghost" id="cf-telegram-resume">${ctx.tt("Resume automation")}</button></div></article></div>`;

    ctx.$("#cf-telegram-save-summary")?.addEventListener("click", async () => {
      try {
        await ctx.apiCall("/api/telegram/summary-settings", "POST", {
          enabled: !!ctx.$("#cf-telegram-summary-enabled")?.checked,
          daily_summary_time: ctx.$("#cf-telegram-summary-time")?.value || "08:00",
        });
        ctx.toast("Telegram summary settings saved.");
      } catch (error) {
        ctx.toast(error.message || "Could not save Telegram settings.", "error");
      }
    });
    ctx.$("#cf-telegram-pause")?.addEventListener("click", async () => {
      try {
        await ctx.apiCall("/api/telegram/pause", "POST", { paused: true });
        ctx.toast("Automation paused for this account.");
      } catch (error) {
        ctx.toast(error.message || "Could not pause automation.", "error");
      }
    });
    ctx.$("#cf-telegram-resume")?.addEventListener("click", async () => {
      try {
        await ctx.apiCall("/api/telegram/pause", "POST", { paused: false });
        ctx.toast("Automation resumed for this account.");
      } catch (error) {
        ctx.toast(error.message || "Could not resume automation.", "error");
      }
    });
  } catch (error) {
    ["#cf-channels-destination-list", "#cf-channels-active-detail", "#cf-channels-defaults", "#cf-channels-telegram"].forEach((selector) => {
      if (ctx.$(selector)) ctx.$(selector).innerHTML = ctx.fail(error.message || "Could not load channels.");
    });
  }
}
