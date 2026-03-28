import { useEffect, useMemo, useState } from "react";

import { apiCall, BootstrapResponse } from "../lib/api";
import { BootPayload, Locale, normalizeLocale } from "../lib/boot";
import { Translator } from "../lib/i18n";
import { EmptyState, ErrorState } from "../ui/States";
import { useToast } from "../ui/ToastProvider";

type SettingsProps = {
  boot: BootPayload;
  translator: Translator;
  loading: boolean;
  error: string | null;
  payload: BootstrapResponse | null;
  refresh: (force?: boolean) => Promise<BootstrapResponse | null>;
  onLocaleChange: (locale: Locale) => Promise<void>;
};

type ProviderModel = { id: string; label?: string };
type ProviderRecord = {
  id: string;
  display_name?: string;
  default_model?: string;
  key_format_hint?: string;
  models?: ProviderModel[];
};

export function SettingsPage({ translator, loading, error, payload, refresh, onLocaleChange }: SettingsProps) {
  const { push } = useToast();
  const settings = (payload?.settings || {}) as Record<string, unknown>;
  const profile = (settings.profile || {}) as Record<string, unknown>;
  const providers = (Array.isArray(settings.providers) ? settings.providers : []) as ProviderRecord[];
  const countries = (((settings.presets || {}) as Record<string, unknown>).countries || []) as Array<Record<string, string>>;

  const [activeProvider, setActiveProvider] = useState("gemini");
  const [model, setModel] = useState("");
  const [fallbackProvider, setFallbackProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [countryCode, setCountryCode] = useState("FR");
  const [timezone, setTimezone] = useState("");
  const [contentLanguage, setContentLanguage] = useState("en");
  const [contentTone, setContentTone] = useState("professional");
  const [rssFeeds, setRssFeeds] = useState("");
  const [approvalMode, setApprovalMode] = useState(false);
  const [uiLanguage, setUiLanguage] = useState("en");

  useEffect(() => {
    const initialProvider = String(profile.ai_provider || providers[0]?.id || "gemini").toLowerCase();
    setActiveProvider(initialProvider);
    const provider = providers.find((item) => item.id === initialProvider) || providers[0];
    setModel(String(profile.ai_model || provider?.default_model || provider?.models?.[0]?.id || ""));
    setFallbackProvider(String(profile.provider_fallback || ""));
    setCountryCode(String(profile.country_code || countries[0]?.country_code || "FR"));
    setTimezone(String(profile.timezone || ""));
    setContentLanguage(String(profile.content_language || "en").toLowerCase());
    setContentTone(String(profile.content_tone || "professional").toLowerCase());
    setRssFeeds(Array.isArray(settings.feeds) ? (settings.feeds as string[]).join("\n") : "");
    setApprovalMode(Boolean(profile.approval_mode));
    setUiLanguage(String(profile.ui_language || "en").toLowerCase());
    setApiKey("");
  }, [countries, profile, providers, settings.feeds]);

  const currentProvider = useMemo(
    () => providers.find((item) => item.id === activeProvider) || providers[0] || null,
    [activeProvider, providers],
  );

  const saveAi = async () => {
    try {
      await apiCall("/api/settings/keys", "POST", {
        provider: activeProvider,
        ai_provider: activeProvider,
        model,
        ai_model: model,
        provider_fallback: fallbackProvider,
        ai_key: apiKey,
      });
      push(translator.tr("AI settings saved."));
      await refresh(true);
      setApiKey("");
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not save AI settings."), "error");
    }
  };

  const testAi = async () => {
    try {
      const result = await apiCall<{ valid?: boolean; error?: string }>("/api/settings/test-ai", "POST", {
        provider: activeProvider,
        ai_provider: activeProvider,
        model,
        ai_model: model,
        provider_fallback: fallbackProvider,
        ai_key: apiKey,
      });
      push(translator.tr(Boolean(result.valid) ? "AI key test passed." : (result.error || "AI key test failed.")), result.valid ? "success" : "error");
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not test the AI key."), "error");
    }
  };

  const saveProfile = async () => {
    try {
      await apiCall("/api/settings/profile", "POST", {
        country_code: countryCode,
        timezone: timezone,
        content_language: contentLanguage,
        content_tone: contentTone,
      });
      push(translator.tr("Content defaults saved."));
      await refresh(true);
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not save content defaults."), "error");
    }
  };

  const applyPreset = async () => {
    try {
      await apiCall("/api/settings/presets/apply", "POST", { country_code: countryCode });
      push(translator.tr("Locale preset applied."));
      await refresh(true);
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not apply the preset."), "error");
    }
  };

  const saveWorkflow = async () => {
    try {
      const feeds = rssFeeds.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      await Promise.all([
        apiCall("/api/config/rss-feeds", "POST", { feeds }),
        apiCall("/api/config/approval-mode", "POST", { enabled: approvalMode }),
      ]);
      push(translator.tr("Workflow defaults saved."));
      await refresh(true);
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not save workflow defaults."), "error");
    }
  };

  const saveInterface = async () => {
    try {
      await onLocaleChange(normalizeLocale(uiLanguage));
      push(translator.tr("Interface language updated."));
      await refresh(true);
    } catch (caught) {
      push(caught instanceof Error ? caught.message : translator.tr("Could not save interface settings."), "error");
    }
  };

  return (
    <section className="cf-screen">
      <header className="cf-page-intro">
        <div>
          <h1 className="cf-page-title">{translator.tr("Settings")}</h1>
          <p className="cf-page-copy">{translator.tr("AI providers, locale defaults, and workflow controls.")}</p>
        </div>
      </header>

      {error && !payload ? (
        <article className="cf-card cf-panel">
          <ErrorState title={translator.tr("Something failed to load")} copy={translator.maybeTr(error)} />
        </article>
      ) : null}

      <section className="cf-settings-flow">
        <article className="cf-card cf-panel">
          <div className="cf-settings-head">
            <div>
              <div className="cf-label">{translator.tr("Bring your own AI")}</div>
              <h2 className="cf-page-title">{translator.tr("Provider and model")}</h2>
            </div>
            <div className="cf-inline-note">{translator.tr("{provider} selected", { provider: currentProvider?.display_name || translator.tr("Provider") })}</div>
          </div>
          {providers.length ? (
            <>
              <div id="cf-settings-providers" className="cf-pill-group">
                {providers.map((provider) => (
                  <button key={provider.id} type="button" className={`cf-pill ${provider.id === activeProvider ? "is-active" : ""}`} onClick={() => {
                    setActiveProvider(provider.id);
                    setModel(provider.default_model || provider.models?.[0]?.id || "");
                  }}>
                    {provider.display_name || provider.id}
                  </button>
                ))}
              </div>
              <div className="cf-settings-grid">
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-react-provider-model">{translator.tr("Model")}</label>
                  <select id="cf-react-provider-model" className="cf-select" value={model} onChange={(event) => setModel(event.target.value)}>
                    {(currentProvider?.models || []).map((item) => (
                      <option key={item.id} value={item.id}>{item.label || item.id}</option>
                    ))}
                  </select>
                </div>
                <div className="cf-field">
                  <label className="cf-field-label" htmlFor="cf-react-provider-fallback">{translator.tr("Fallback provider")}</label>
                  <select id="cf-react-provider-fallback" className="cf-select" value={fallbackProvider} onChange={(event) => setFallbackProvider(event.target.value)}>
                    <option value="">{translator.tr("No fallback")}</option>
                    {providers.map((provider) => (
                      <option key={provider.id} value={provider.id}>{provider.display_name || provider.id}</option>
                    ))}
                  </select>
                </div>
                <div className="cf-field cf-field-span">
                  <label className="cf-field-label" htmlFor="cf-react-provider-key">{translator.tr("API key")}</label>
                  <input id="cf-react-provider-key" className="cf-input" type="password" value={apiKey} placeholder={currentProvider?.key_format_hint || ""} onChange={(event) => setApiKey(event.target.value)} />
                </div>
              </div>
              <div className="cf-inline-actions">
                <button type="button" className="cf-btn-ghost" onClick={() => void testAi()}>{translator.tr("Test AI Key")}</button>
                <button type="button" className="cf-btn" onClick={() => void saveAi()}>{translator.tr("Save AI Settings")}</button>
              </div>
            </>
          ) : (
            <EmptyState title={translator.tr("No provider available")} copy={translator.tr("AI providers are not configured yet.")} />
          )}
        </article>

        <section className="cf-grid cols-2">
          <article className="cf-card cf-panel">
            <div className="cf-section-head cf-section-head-quiet">
              <span className="cf-label">{translator.tr("Content defaults")}</span>
            </div>
            <div className="cf-settings-grid">
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-react-country">{translator.tr("Country")}</label>
                <select id="cf-react-country" className="cf-select" value={countryCode} onChange={(event) => setCountryCode(event.target.value)}>
                  {countries.map((country) => (
                    <option key={country.country_code} value={country.country_code}>{country.label}</option>
                  ))}
                </select>
              </div>
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-react-timezone">{translator.tr("Timezone")}</label>
                <input id="cf-react-timezone" className="cf-input" value={timezone} onChange={(event) => setTimezone(event.target.value)} />
              </div>
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-react-content-language">{translator.tr("Default content language")}</label>
                <select id="cf-react-content-language" className="cf-select" value={contentLanguage} onChange={(event) => setContentLanguage(event.target.value)}>
                  <option value="en">{translator.tr("English")}</option>
                  <option value="fr">{translator.tr("French")}</option>
                  <option value="ar">{translator.tr("Arabic")}</option>
                </select>
              </div>
              <div className="cf-field">
                <label className="cf-field-label" htmlFor="cf-react-content-tone">{translator.tr("Content tone")}</label>
                <select id="cf-react-content-tone" className="cf-select" value={contentTone} onChange={(event) => setContentTone(event.target.value)}>
                  <option value="professional">{translator.tr("Professional")}</option>
                  <option value="casual">{translator.tr("Casual")}</option>
                  <option value="educational">{translator.tr("Educational")}</option>
                  <option value="humorous">{translator.tr("Humorous")}</option>
                </select>
              </div>
            </div>
            <div className="cf-inline-actions">
              <button type="button" className="cf-btn-ghost" onClick={() => void applyPreset()}>{translator.tr("Apply Locale Preset")}</button>
              <button type="button" className="cf-btn" onClick={() => void saveProfile()}>{translator.tr("Save Content Defaults")}</button>
            </div>
          </article>

          <article className="cf-card cf-panel">
            <div className="cf-section-head cf-section-head-quiet">
              <span className="cf-label">{translator.tr("Workflow defaults")}</span>
            </div>
            <div className="cf-field">
              <label className="cf-field-label" htmlFor="cf-react-rss">{translator.tr("RSS feeds")}</label>
              <textarea id="cf-react-rss" className="cf-textarea" rows={6} value={rssFeeds} onChange={(event) => setRssFeeds(event.target.value)} />
            </div>
            <label className="cf-toggle-card">
              <input type="checkbox" checked={approvalMode} onChange={(event) => setApprovalMode(event.target.checked)} />
              <span>
                <strong>{translator.tr("Manual approval mode")}</strong>
                <small>{translator.tr("Queue supported posts for review before they can be scheduled.")}</small>
              </span>
            </label>
            <div className="cf-inline-actions">
              <button type="button" className="cf-btn" onClick={() => void saveWorkflow()}>{translator.tr("Save Workflow Defaults")}</button>
            </div>
          </article>
        </section>

        <article className="cf-card cf-panel">
          <div className="cf-section-head cf-section-head-quiet">
            <span className="cf-label">{translator.tr("Interface and locale")}</span>
          </div>
          <div className="cf-grid cols-3">
            <div className="cf-field">
              <label className="cf-field-label" htmlFor="cf-react-ui-language">{translator.tr("Navigation language")}</label>
              <select id="cf-react-ui-language" className="cf-select" value={uiLanguage} onChange={(event) => setUiLanguage(event.target.value)}>
                <option value="en">EN</option>
                <option value="fr">FR</option>
                <option value="ar">AR</option>
              </select>
            </div>
          </div>
          <div className="cf-inline-actions">
            <button type="button" className="cf-btn" onClick={() => void saveInterface()}>{translator.tr("Save Interface Settings")}</button>
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
