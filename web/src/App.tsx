import { useCallback, useEffect, useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { fetchBootstrap, BootstrapResponse } from "./lib/api";
import { AppPage, BootPayload, Locale, getBoot, normalizeLocale } from "./lib/boot";
import { applyDocumentLocale, createTranslator } from "./lib/i18n";
import { AppShell } from "./ui/AppShell";
import { CinematicBackground } from "./ui/CinematicBackground";
import { ToastProvider, useToast } from "./ui/ToastProvider";
import { PageTransition } from "./ui/primitives";
import { DashboardPage } from "./routes/DashboardPage";
import { StudioPage } from "./routes/StudioPage";
import { ChannelsPage } from "./routes/ChannelsPage";
import { SettingsPage } from "./routes/SettingsPage";
import { DiagnosticsPage } from "./routes/DiagnosticsPage";

function useCurrentPage(boot: BootPayload): AppPage {
  const location = useLocation();
  if (location.pathname === boot.urls.studio || location.pathname.startsWith(`${boot.urls.studio}/`)) {
    return "studio";
  }
  if (location.pathname === boot.urls.channels || location.pathname.startsWith(`${boot.urls.channels}/`)) {
    return "channels";
  }
  if (location.pathname === boot.urls.settings || location.pathname.startsWith(`${boot.urls.settings}/`)) {
    return "settings";
  }
  if (location.pathname === boot.urls.diagnostics || location.pathname.startsWith(`${boot.urls.diagnostics}/`)) {
    return "diagnostics";
  }
  return "dashboard";
}

function ShellApp({ boot }: { boot: BootPayload }) {
  const [locale, setLocale] = useState<Locale>(normalizeLocale(boot.locale));
  const [data, setData] = useState<BootstrapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { push } = useToast();
  const page = useCurrentPage(boot);
  const location = useLocation();

  const translator = useMemo(() => createTranslator(boot.i18nCatalog, locale), [boot.i18nCatalog, locale]);

  useEffect(() => {
    applyDocumentLocale(locale);
    const pageTitleKey: Record<AppPage, string> = {
      dashboard: "Dashboard",
      studio: "Studio",
      channels: "Channels",
      settings: "Settings",
      diagnostics: "Diagnostics",
    };
    document.title = `${translator.tr(pageTitleKey[page])} | Content Factory`;
  }, [locale, page, translator]);

  const refresh = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchBootstrap(page, force);
      setData(payload);
      return payload;
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Could not load application data.";
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void refresh(false);
  }, [refresh]);

  const handleLocaleChange = useCallback(async (nextLocale: Locale) => {
    const previous = locale;
    setLocale(nextLocale);
    try {
      const response = await fetch("/api/settings/profile", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": boot.csrfToken,
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ ui_language: nextLocale.toLowerCase() }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Could not save the language setting.");
      }
      push(translator.tr("Navigation language updated."));
      await refresh(true);
    } catch (caught) {
      setLocale(previous);
      push(caught instanceof Error ? caught.message : translator.tr("Could not save the language setting."), "error");
    }
  }, [boot.csrfToken, locale, push, refresh, translator]);

  return (
    <AppShell
      boot={boot}
      translator={translator}
      locale={locale}
      page={page}
      shell={(data?.shell as Record<string, unknown>) || null}
      onLocaleChange={handleLocaleChange}
    >
      <PageTransition pageKey={location.pathname}>
        <Routes>
          <Route
            path={boot.urls.dashboard}
            element={<DashboardPage boot={boot} translator={translator} loading={loading} error={error} payload={data} refresh={refresh} />}
          />
          <Route
            path={boot.urls.studio}
            element={<StudioPage boot={boot} translator={translator} loading={loading} error={error} payload={data} refresh={refresh} />}
          />
          <Route
            path={boot.urls.channels}
            element={<ChannelsPage boot={boot} translator={translator} loading={loading} error={error} payload={data} refresh={refresh} />}
          />
          <Route
            path={boot.urls.settings}
            element={<SettingsPage boot={boot} translator={translator} loading={loading} error={error} payload={data} refresh={refresh} onLocaleChange={handleLocaleChange} />}
          />
          <Route
            path={boot.urls.diagnostics}
            element={<DiagnosticsPage boot={boot} translator={translator} loading={loading} error={error} payload={data} refresh={refresh} />}
          />
          <Route path="/" element={<Navigate to={boot.urls.dashboard} replace />} />
          <Route path="*" element={<Navigate to={boot.urls.dashboard} replace />} />
        </Routes>
      </PageTransition>
    </AppShell>
  );
}

export default function App() {
  const boot = useMemo(() => getBoot(), []);

  return (
    <BrowserRouter>
      <ToastProvider>
        <CinematicBackground />
        <ShellApp boot={boot} />
      </ToastProvider>
    </BrowserRouter>
  );
}
