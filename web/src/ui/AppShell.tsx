import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import { AppPage, BootPayload, Locale } from "../lib/boot";
import { Translator } from "../lib/i18n";

type ShellPayload = {
  setup?: {
    steps?: Array<{
      id: string;
      label: string;
      description: string;
      action_label?: string;
      action_url?: string;
      completed: boolean;
      optional?: boolean;
    }>;
    all_required_complete?: boolean;
    next_required_step?: string;
  };
  status?: {
    can_post?: boolean;
    post_reason?: string;
    ban_detector?: {
      status?: string;
    };
  };
};

function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

const navItems: Array<{ page: AppPage; icon: string; label: string; urlKey: keyof BootPayload["urls"] }> = [
  { page: "dashboard", icon: "fa-house", label: "Dashboard", urlKey: "dashboard" },
  { page: "studio", icon: "fa-wand-magic-sparkles", label: "Studio", urlKey: "studio" },
  { page: "channels", icon: "fa-satellite-dish", label: "Channels", urlKey: "channels" },
  { page: "settings", icon: "fa-gear", label: "Settings", urlKey: "settings" },
  { page: "diagnostics", icon: "fa-stethoscope", label: "Diagnostics", urlKey: "diagnostics" },
];

export function AppShell({
  boot,
  translator,
  locale,
  page,
  shell,
  onLocaleChange,
  children,
}: {
  boot: BootPayload;
  translator: Translator;
  locale: Locale;
  page: AppPage;
  shell: ShellPayload | null;
  onLocaleChange: (locale: Locale) => void;
  children: ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => localStorage.getItem("cf_sidebar_collapsed") === "1");
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    document.body.classList.toggle("is-sidebar-collapsed", sidebarCollapsed);
    localStorage.setItem("cf_sidebar_collapsed", sidebarCollapsed ? "1" : "0");
  }, [sidebarCollapsed]);

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setUserMenuOpen(false);
    };
    document.addEventListener("click", handleClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("click", handleClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const setup = shell?.setup || {};
  const status = shell?.status || {};
  const requiredSteps = (setup.steps || []).filter((step) => !step.optional);
  const completedRequired = requiredSteps.filter((step) => step.completed).length;
  const score = useMemo(() => {
    if (!setup.all_required_complete) {
      return requiredSteps.length ? Math.round((completedRequired / requiredSteps.length) * 100) : 100;
    }
    if (status.can_post) return 100;
    return status.ban_detector?.status === "watch" ? 74 : 62;
  }, [completedRequired, requiredSteps.length, setup.all_required_complete, status.ban_detector?.status, status.can_post]);

  const setupReady = setup.all_required_complete && status.can_post;
  const showSetupBar = !sidebarCollapsed && page === "dashboard" && !setupReady;
  const pageTitles: Record<AppPage, string> = {
    dashboard: translator.tr("Dashboard"),
    studio: translator.tr("Studio"),
    channels: translator.tr("Channels"),
    settings: translator.tr("Settings"),
    diagnostics: translator.tr("Diagnostics"),
  };
  const pageTitle = pageTitles[page];

  return (
    <div className={cn("cf-shell", sidebarCollapsed && "is-sidebar-collapsed")} data-app-page={page}>
      <motion.aside
        className="cf-sidebar"
        aria-label={translator.tr("Primary navigation")}
        animate={sidebarCollapsed ? { width: "var(--sidebar-w-collapsed)" } : { width: "var(--sidebar-w)" }}
        transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="cf-sidebar-head">
          <a className="cf-brand" href={boot.urls.dashboard}>
            <span className="cf-brand-mark">CF</span>
            <AnimatePresence>
              {!sidebarCollapsed ? (
                <motion.span
                  className="cf-brand-copy"
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: "auto" }}
                  exit={{ opacity: 0, width: 0 }}
                  transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                >
                  <span className="cf-brand-title">Content Factory</span>
                </motion.span>
              ) : null}
            </AnimatePresence>
          </a>
          <button
            type="button"
            className="cf-sidebar-toggle"
            aria-label={translator.tr("Toggle rail")}
            aria-pressed={sidebarCollapsed ? "true" : "false"}
            onClick={() => setSidebarCollapsed((current) => !current)}
          >
            <i className={cn("fa-solid", sidebarCollapsed ? "fa-angles-right" : "fa-angles-left")} />
          </button>
        </div>

        <nav className="cf-sidebar-nav" aria-label={translator.tr("Primary")}>
          {navItems.map(({ page: navPage, icon, label, urlKey }) => (
            <NavLink
              key={navPage}
              to={boot.urls[urlKey]}
              className={({ isActive }) => cn("cf-sidebar-nav-link", (isActive || page === navPage) && "is-active")}
              title={sidebarCollapsed ? translator.tr(label) : undefined}
            >
              <i className={cn("fa-solid", icon, "cf-sidebar-nav-icon")} />
              <AnimatePresence>
                {!sidebarCollapsed ? (
                  <motion.span
                    className="cf-sidebar-nav-label"
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: "auto" }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                  >
                    {translator.tr(label)}
                  </motion.span>
                ) : null}
              </AnimatePresence>
            </NavLink>
          ))}
        </nav>

        <div className="cf-sidebar-foot">
          <AnimatePresence>
            {showSetupBar ? (
              <motion.div
                className="cf-sidebar-setup-bar"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
              >
                <div className="cf-sidebar-setup-label">{translator.tr("Setup {score}%", { score })}</div>
                <div className="cf-sidebar-setup-track">
                  <motion.div
                    className="cf-sidebar-setup-fill"
                    initial={{ width: 0 }}
                    animate={{ width: `${score}%` }}
                    transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                  />
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <a className={cn("cf-sidebar-cta", sidebarCollapsed && "is-icon-only")} href={boot.urls.studio} title={translator.tr("New Post")}>
            <i className="fa-solid fa-plus" />
            <AnimatePresence>
              {!sidebarCollapsed ? (
                <motion.span
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: "auto" }}
                  exit={{ opacity: 0, width: 0 }}
                  transition={{ duration: 0.18 }}
                >
                  {translator.tr("New Post")}
                </motion.span>
              ) : null}
            </AnimatePresence>
          </a>
        </div>
      </motion.aside>

      <main className="cf-main">
        <header className="cf-topbar">
          <div className="cf-topbar-left">
            <span className="cf-topbar-page-title">{pageTitle}</span>
          </div>
          <div className="cf-topbar-right">
            <span className="cf-live">{translator.tr("Live")}</span>
            <select
              className="cf-lang"
              aria-label={translator.tr("System language")}
              value={locale}
              onChange={(event) => onLocaleChange(event.target.value as Locale)}
            >
              <option value="EN">EN</option>
              <option value="FR">FR</option>
              <option value="AR">AR</option>
            </select>
            <div className="cf-user-menu-wrap" ref={userMenuRef}>
              <button
                type="button"
                className="cf-user-btn"
                aria-expanded={userMenuOpen ? "true" : "false"}
                aria-haspopup="true"
                onClick={() => setUserMenuOpen((current) => !current)}
              >
                {boot.user.email || translator.tr("Account")}
              </button>
              <div className="cf-user-popover" hidden={!userMenuOpen}>
                <div className="cf-user-popover-label">{translator.tr("Account")}</div>
                <a href={boot.urls.diagnostics} className="cf-user-popover-link" onClick={() => setUserMenuOpen(false)}>
                  {translator.tr("Diagnostics")}
                </a>
                <form method="post" action={boot.urls.logout} className="cf-user-popover-form">
                  <input type="hidden" name="csrf_token" value={boot.csrfToken} />
                  <button type="submit" className="cf-user-popover-link cf-user-popover-button" onClick={() => setUserMenuOpen(false)}>
                    {translator.tr("Sign out")}
                  </button>
                </form>
              </div>
            </div>
          </div>
        </header>

        <section className="cf-content">{children}</section>
      </main>

      <nav className="cf-dock" aria-label={translator.tr("Primary mobile navigation")}>
        {navItems.map(({ page: navPage, label, urlKey }) => (
          <NavLink key={navPage} to={boot.urls[urlKey]} className={({ isActive }) => cn("cf-dock-link", (isActive || page === navPage) && "is-active")}>
            {translator.tr(label)}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
