export function createShell(ctx) {
  function closeUserPopover() {
    const menu = ctx.$("#cf-user-menu");
    const popover = ctx.$("#cf-user-popover");
    if (popover) popover.hidden = true;
    menu?.setAttribute("aria-expanded", "false");
  }

  function syncSidebarToggle() {
    const collapsed = document.body.classList.contains("is-sidebar-collapsed");
    ctx.$("#cf-sidebar-toggle")?.setAttribute("aria-pressed", collapsed ? "true" : "false");
    const icon = ctx.$("#cf-sidebar-toggle-icon");
    if (icon) icon.className = `fa-solid ${collapsed ? "fa-angles-right" : "fa-angles-left"}`;
  }

  function setSidebarCollapsed(collapsed) {
    document.body.classList.toggle("is-sidebar-collapsed", !!collapsed);
    localStorage.setItem("cf_sidebar_collapsed", collapsed ? "1" : "0");
    syncSidebarToggle();
  }

  function applyLocale(lang) {
    ctx.state.currentLocale = String(lang || "EN").toUpperCase();
    document.documentElement.lang = ctx.localeCode(ctx.state.currentLocale);
    document.documentElement.dir = ctx.state.currentLocale === "AR" ? "rtl" : "ltr";
    ctx.$("#cf-sidebar-toggle")?.setAttribute("title", ctx.tr("Toggle rail"));
    ctx.$("#cf-sidebar-toggle")?.setAttribute("aria-label", ctx.tr("Toggle rail"));
    syncSidebarToggle();
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = ctx.tr(element.dataset.i18n);
    });
  }

  async function hydrateShell() {
    try {
      const bootstrap = await ctx.loadBootstrap();
      const shell = bootstrap.shell || {};
      const setup = shell.setup || {};
      const status = shell.status || {};
      const requiredSteps = (setup.steps || []).filter((step) => !step.optional);
      const completedRequired = requiredSteps.filter((step) => step.completed).length;
      const nextStep = (setup.steps || []).find((step) => step.id === setup.next_required_step);
      if (!setup.all_required_complete && nextStep && ctx.$("#cf-setup-inline")) {
        ctx.$("#cf-setup-inline").classList.remove("cf-hidden");
        ctx.$("#cf-setup-inline").onclick = () => {
          window.location.href = nextStep.action_url || "/settings";
        };
        ctx.$("#cf-setup-step").textContent = ctx.tr("Step {current} of {total}", { current: completedRequired + 1, total: Math.max(requiredSteps.length, 1) });
        ctx.$("#cf-setup-text").textContent = ctx.maybeTr(nextStep.description || nextStep.label);
      }

      let score = requiredSteps.length ? Math.round((completedRequired / requiredSteps.length) * 100) : 100;
      let kicker = "Setup required";
      if (setup.all_required_complete) {
        score = status.can_post ? 100 : ((status.ban_detector || {}).status === "watch" ? 74 : 62);
        kicker = status.can_post ? "Publishing ready" : "Action needed";
      }

      if (ctx.$("#cf-shell-score")) ctx.$("#cf-shell-score").textContent = `${score}%`;
      if (ctx.$("#cf-shell-kicker")) ctx.$("#cf-shell-kicker").textContent = ctx.tr(kicker);
      if (ctx.$("#cf-shell-score-copy")) ctx.$("#cf-shell-score-copy").textContent = ctx.maybeTr(status.post_reason || "Finish setup to unlock publishing.");
    } catch (error) {
      if (ctx.$("#cf-shell-score-copy")) ctx.$("#cf-shell-score-copy").textContent = ctx.maybeTr(error.message || "Could not load account state.");
    }
  }

  function initShell() {
    applyLocale(ctx.$("#cf-system-language")?.value || document.body.dataset.systemLang || "EN");
    setSidebarCollapsed(localStorage.getItem("cf_sidebar_collapsed") === "1");
    ctx.$("#cf-sidebar-toggle")?.addEventListener("click", () => setSidebarCollapsed(!document.body.classList.contains("is-sidebar-collapsed")));

    const menu = ctx.$("#cf-user-menu");
    const popover = ctx.$("#cf-user-popover");
    closeUserPopover();
    menu?.addEventListener("click", (event) => {
      event.stopPropagation();
      const open = !!popover?.hidden;
      menu.setAttribute("aria-expanded", open ? "true" : "false");
      if (popover) popover.hidden = !open;
    });
    document.addEventListener("click", (event) => {
      if (popover && !popover.hidden && !popover.contains(event.target) && !menu?.contains(event.target)) {
        closeUserPopover();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeUserPopover();
    });
    popover?.querySelectorAll("a, button").forEach((node) => node.addEventListener("click", () => closeUserPopover()));
    ctx.$("#cf-system-language")?.addEventListener("change", async (event) => {
      const value = String(event.target.value || "EN").toUpperCase();
      applyLocale(value);
      if (ctx.$("#cf-settings-ui-language")) ctx.$("#cf-settings-ui-language").value = value.toLowerCase();
      try {
        await ctx.apiCall("/api/settings/profile", "POST", { ui_language: value.toLowerCase() });
        ctx.toast("Navigation language updated.");
        if (typeof ctx.rehydrateCurrentPage === "function") ctx.rehydrateCurrentPage();
      } catch (error) {
        ctx.toast(error.message || "Could not save the language setting.", "error");
      }
    });
    hydrateShell();
  }

  return {
    initShell,
    applyLocale,
    hydrateShell,
  };
}
