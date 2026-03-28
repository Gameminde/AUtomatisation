function renderProviderForm(ctx, providers, profile, activeProvider) {
  const provider = providers.find((item) => item.id === activeProvider) || providers[0];
  document.querySelectorAll("#cf-settings-providers .cf-provider-card").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.providerId === activeProvider);
  });
  ctx.$("#cf-settings-model").innerHTML = (provider?.models || []).map((model) => `<option value="${ctx.esc(model.id)}" ${model.id === (profile.ai_model || provider.default_model) ? "selected" : ""}>${ctx.esc(model.label || model.id)}</option>`).join("");
  ctx.$("#cf-settings-fallback").innerHTML = [`<option value="">${ctx.tt("No fallback")}</option>`, ...providers.map((item) => `<option value="${ctx.esc(item.id)}" ${item.id === String(profile.provider_fallback || "") ? "selected" : ""}>${ctx.esc(item.display_name || item.id)}</option>`)].join("");
  if (ctx.$("#cf-settings-ai-status")) ctx.$("#cf-settings-ai-status").textContent = ctx.tr("{provider} selected", { provider: provider?.display_name || ctx.tr("Provider") });
}

function aiPayload(ctx) {
  const provider = ctx.$("#cf-settings-providers .cf-provider-card.is-active")?.dataset.providerId || "gemini";
  return {
    provider,
    ai_provider: provider,
    model: ctx.$("#cf-settings-model")?.value || "",
    ai_model: ctx.$("#cf-settings-model")?.value || "",
    provider_fallback: ctx.$("#cf-settings-fallback")?.value || "",
    ai_key: ctx.$("#cf-settings-api-key")?.value || "",
  };
}

export async function initSettings(ctx, shell) {
  try {
    const bootstrap = await ctx.loadBootstrap();
    const settings = bootstrap.settings || {};
    const profile = settings.profile || {};
    const providers = settings.providers || [];
    const countries = (settings.presets || {}).countries || [];
    const activeProvider = String(profile.ai_provider || providers[0]?.id || "gemini").toLowerCase();

    ctx.$("#cf-settings-providers").innerHTML = providers.map((provider) => `<button type="button" class="cf-provider-card ${provider.id === activeProvider ? "is-active" : ""}" data-provider-id="${ctx.esc(provider.id)}"><div class="cf-format-name">${ctx.esc(provider.display_name || provider.id)}</div><div class="cf-format-copy">${ctx.esc(ctx.maybeTr(provider.key_format_hint || provider.status || "Configured per user"))}</div></button>`).join("");
    ctx.$("#cf-settings-providers").querySelectorAll("[data-provider-id]").forEach((button) => button.addEventListener("click", () => renderProviderForm(ctx, providers, profile, button.dataset.providerId)));
    renderProviderForm(ctx, providers, profile, activeProvider);

    ctx.$("#cf-settings-country").innerHTML = countries.map((country) => `<option value="${ctx.esc(country.country_code)}" ${country.country_code === profile.country_code ? "selected" : ""}>${ctx.esc(country.label)}</option>`).join("");
    ctx.$("#cf-settings-preset").innerHTML = countries.map((country) => `<option value="${ctx.esc(country.country_code)}" ${country.country_code === profile.country_code ? "selected" : ""}>${ctx.esc(country.label)}</option>`).join("");
    ctx.$("#cf-settings-content-language").value = String(profile.content_language || "en").toLowerCase();
    ctx.$("#cf-settings-tone").value = String(profile.content_tone || "professional").toLowerCase();
    ctx.$("#cf-settings-timezone").value = profile.timezone || "";
    ctx.$("#cf-settings-rss").value = Array.isArray(settings.feeds) ? settings.feeds.join("\n") : "";
    ctx.$("#cf-settings-approval-mode").checked = !!profile.approval_mode;
    ctx.$("#cf-settings-ui-language").value = String(profile.ui_language || (ctx.$("#cf-system-language")?.value || "EN")).toLowerCase();
    if (ctx.$("#cf-system-language")) ctx.$("#cf-system-language").value = String(profile.ui_language || (ctx.$("#cf-system-language")?.value || "EN")).toUpperCase();
    shell.applyLocale(ctx.$("#cf-system-language")?.value || "EN");

    ctx.$("#cf-settings-test-key")?.addEventListener("click", async () => {
      try {
        const result = await ctx.apiCall("/api/settings/test-ai", "POST", aiPayload(ctx));
        ctx.toast(result.valid ? "AI key test passed." : (result.error || "AI key test failed."), result.valid ? "success" : "error");
      } catch (error) {
        ctx.toast(error.message || "Could not test the AI key.", "error");
      }
    });

    ctx.$("#cf-settings-save-ai")?.addEventListener("click", async () => {
      try {
        await ctx.apiCall("/api/settings/keys", "POST", aiPayload(ctx));
        await ctx.refreshBootstrap();
        ctx.toast("AI settings saved.");
      } catch (error) {
        ctx.toast(error.message || "Could not save AI settings.", "error");
      }
    });

    ctx.$("#cf-settings-save-profile")?.addEventListener("click", async () => {
      try {
        await ctx.apiCall("/api/settings/profile", "POST", {
          country_code: ctx.$("#cf-settings-country")?.value || countries[0]?.country_code || "FR",
          timezone: ctx.$("#cf-settings-timezone")?.value || "",
          content_language: ctx.$("#cf-settings-content-language")?.value || "en",
          content_tone: ctx.$("#cf-settings-tone")?.value || "professional",
        });
        await ctx.refreshBootstrap();
        ctx.toast("Content defaults saved.");
      } catch (error) {
        ctx.toast(error.message || "Could not save content defaults.", "error");
      }
    });

    ctx.$("#cf-settings-apply-preset")?.addEventListener("click", async () => {
      try {
        const result = await ctx.apiCall("/api/settings/presets/apply", "POST", {
          country_code: ctx.$("#cf-settings-preset")?.value || ctx.$("#cf-settings-country")?.value || "FR",
        });
        await ctx.refreshBootstrap();
        ctx.toast("Locale preset applied.");
        if (ctx.$("#cf-settings-country")) ctx.$("#cf-settings-country").value = result.profile?.country_code || ctx.$("#cf-settings-country").value;
        if (ctx.$("#cf-settings-timezone")) ctx.$("#cf-settings-timezone").value = result.profile?.timezone || ctx.$("#cf-settings-timezone").value;
      } catch (error) {
        ctx.toast(error.message || "Could not apply the preset.", "error");
      }
    });

    ctx.$("#cf-settings-save-publishing")?.addEventListener("click", async () => {
      try {
        const feeds = (ctx.$("#cf-settings-rss")?.value || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
        await Promise.all([
          ctx.apiCall("/api/config/rss-feeds", "POST", { feeds }),
          ctx.apiCall("/api/config/approval-mode", "POST", { enabled: !!ctx.$("#cf-settings-approval-mode")?.checked }),
        ]);
        await ctx.refreshBootstrap();
        ctx.toast("Workflow defaults saved.");
      } catch (error) {
        ctx.toast(error.message || "Could not save workflow defaults.", "error");
      }
    });

    ctx.$("#cf-settings-save-interface")?.addEventListener("click", async () => {
      try {
        const value = ctx.$("#cf-settings-ui-language")?.value || "en";
        await ctx.apiCall("/api/settings/profile", "POST", { ui_language: value });
        if (ctx.$("#cf-system-language")) ctx.$("#cf-system-language").value = value.toUpperCase();
        shell.applyLocale(value.toUpperCase());
        ctx.toast("Interface language updated.");
        if (typeof ctx.rehydrateCurrentPage === "function") ctx.rehydrateCurrentPage();
      } catch (error) {
        ctx.toast(error.message || "Could not save interface settings.", "error");
      }
    });
  } catch (error) {
    if (ctx.$(".cf-settings-flow")) ctx.$(".cf-settings-flow").innerHTML = ctx.fail(error.message || "Could not load settings.");
  }
}
