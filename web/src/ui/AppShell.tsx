import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { NavLink } from "react-router-dom";

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
      if (event.key === "Escape") {
        setUserMenuOpen(false);
      }
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
  const nextStep = (setup.steps || []).find((step) => step.id === setup.next_required_step);
  const score = useMemo(() => {
    if (!setup.all_required_complete) {
      return requiredSteps.length ? Math.round((completedRequired / requiredSteps.length) * 100) : 100;
    }
    if (status.can_post) return 100;
    return status.ban_detector?.status === "watch" ? 74 : 62;
  }, [completedRequired, requiredSteps.length, setup.all_required_complete, status.ban_detector?.status, status.can_post]);
  const kicker = !setup.all_required_complete
    ? translator.tr("Setup required")
    : status.can_post
      ? translator.tr("Publishing ready")
      : translator.tr("Action needed");
  const pageTitles: Record<AppPage, string> = {
    dashboard: translator.tr("Dashboard"),
    studio: translator.tr("Studio"),
    channels: translator.tr("Channels"),
    settings: translator.tr("Settings"),
    diagnostics: translator.tr("Diagnostics"),
  };
  const pageTitle = pageTitles[page];

  return (
    <div className="cf-shell">
      <aside className="cf-sidebar" aria-label="Primary">
        <div className="cf-sidebar-head">
          <a className="cf-brand" href={boot.urls.dashboard}>
            <span className="cf-brand-mark">CF</span>
            <span className="cf-brand-copy">
              <span className="cf-brand-title">Content Factory</span>
              <span className="cf-brand-sub">{translator.tr("Editorial control for Facebook and Instagram")}</span>
            </span>
          </a>
          <button
            type="button"
            className="cf-sidebar-toggle"
            id="cf-sidebar-toggle"
            aria-label={translator.tr("Toggle rail")}
            title={translator.tr("Toggle rail")}
            aria-pressed={sidebarCollapsed ? "true" : "false"}
            onClick={() => setSidebarCollapsed((current) => !current)}
          >
            <i className={cn("fa-solid", sidebarCollapsed ? "fa-angles-right" : "fa-angles-left")} id="cf-sidebar-toggle-icon" />
          </button>
        </div>

        <section className="cf-sidebar-hero">
          <div className="cf-sidebar-kicker" id="cf-shell-kicker">{kicker}</div>
          <div className="cf-sidebar-statement">
            <div className="cf-sidebar-value" id="cf-shell-score">{score}%</div>
            <p className="cf-sidebar-copy" id="cf-shell-score-copy">
              {translator.maybeTr(status.post_reason || "Finish setup to unlock publishing.")}
            </p>
          </div>
        </section>
      </aside>

      <main className="cf-main">
        <header className="cf-topbar">
          <div className="cf-topbar-left">
            <nav className="cf-topnav" aria-label="Primary navigation">
              <NavLink to={boot.urls.dashboard} className={({ isActive }) => cn("cf-topnav-link", isActive && "is-active")}>
                <span>{translator.tr("Dashboard")}</span>
              </NavLink>
              <NavLink to={boot.urls.studio} className={({ isActive }) => cn("cf-topnav-link", isActive && "is-active")}>
                <span>{translator.tr("Studio")}</span>
              </NavLink>
              <NavLink to={boot.urls.channels} className={({ isActive }) => cn("cf-topnav-link", isActive && "is-active")}>
                <span>{translator.tr("Channels")}</span>
              </NavLink>
              <NavLink to={boot.urls.settings} className={({ isActive }) => cn("cf-topnav-link", isActive && "is-active")}>
                <span>{translator.tr("Settings")}</span>
              </NavLink>
              <NavLink to={boot.urls.diagnostics} className={({ isActive }) => cn("cf-topnav-link", isActive && "is-active")}>
                <span>{translator.tr("Diagnostics")}</span>
              </NavLink>
            </nav>
          </div>

          <div className="cf-topbar-right">
            <span className="cf-live">{translator.tr("Live")}</span>
            <select
              className="cf-lang"
              id="cf-system-language"
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
                id="cf-user-menu"
                aria-expanded={userMenuOpen ? "true" : "false"}
                aria-haspopup="true"
                onClick={() => setUserMenuOpen((current) => !current)}
              >
                {boot.user.email || translator.tr("Account")}
              </button>
              <div className="cf-user-popover" id="cf-user-popover" hidden={!userMenuOpen}>
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

        <section className="cf-context-bar">
          <div className="cf-context-primary">
            <div className="cf-breadcrumb" id="cf-breadcrumb">
              <span className="cf-label">{translator.tr("Workspace")}</span>
              <span className="cf-breadcrumb-sep">/</span>
              <span className="cf-breadcrumb-current">{pageTitle}</span>
            </div>
          </div>
          <div className="cf-context-secondary">
            {!setup.all_required_complete && nextStep ? (
              <button
                type="button"
                className="cf-setup-inline"
                id="cf-setup-inline"
                onClick={() => window.location.assign(nextStep.action_url || boot.urls.settings)}
              >
                <span className="cf-label" id="cf-setup-step">
                  {translator.tr("Step {current} of {total}", {
                    current: completedRequired + 1,
                    total: Math.max(requiredSteps.length, 1),
                  })}
                </span>
                <span id="cf-setup-text">{translator.maybeTr(nextStep.description || nextStep.label)}</span>
              </button>
            ) : null}
          </div>
        </section>

        <section className="cf-content">{children}</section>
      </main>

      <nav className="cf-dock" aria-label="Primary mobile navigation">
        <NavLink to={boot.urls.dashboard} className={({ isActive }) => cn("cf-dock-link", isActive && "is-active")}>
          {translator.tr("Dashboard")}
        </NavLink>
        <NavLink to={boot.urls.studio} className={({ isActive }) => cn("cf-dock-link", isActive && "is-active")}>
          {translator.tr("Studio")}
        </NavLink>
        <NavLink to={boot.urls.channels} className={({ isActive }) => cn("cf-dock-link", isActive && "is-active")}>{translator.tr("Channels")}</NavLink>
        <NavLink to={boot.urls.settings} className={({ isActive }) => cn("cf-dock-link", isActive && "is-active")}>{translator.tr("Settings")}</NavLink>
        <NavLink to={boot.urls.diagnostics} className={({ isActive }) => cn("cf-dock-link", isActive && "is-active")}>{translator.tr("Diagnostics")}</NavLink>
      </nav>
    </div>
  );
}
