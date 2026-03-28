import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BootPayload } from "../lib/boot";
import { createTranslator } from "../lib/i18n";
import { SettingsPage } from "../routes/SettingsPage";
import { ToastProvider } from "../ui/ToastProvider";

const boot: BootPayload = {
  page: "settings",
  locale: "EN",
  dir: "ltr",
  csrfToken: "csrf-token",
  i18nCatalog: {},
  user: { email: "creator@example.com" },
  urls: {
    dashboard: "/app/dashboard",
    studio: "/studio",
    channels: "/channels",
    settings: "/settings",
    diagnostics: "/diagnostics",
    login: "/auth/login",
    logout: "/auth/logout",
  },
};

describe("SettingsPage", () => {
  it("renders provider and profile controls from bootstrap payload", () => {
    render(
      <ToastProvider>
        <SettingsPage
          boot={boot}
          translator={createTranslator({}, "EN")}
          loading={false}
          error={null}
          refresh={async () => null}
          onLocaleChange={vi.fn(async () => undefined)}
          payload={{
            success: true,
            page: "settings",
            shell: {},
            settings: {
              profile: {
                ai_provider: "gemini",
                ai_model: "gemini-2.5-flash",
                country_code: "FR",
                timezone: "Europe/Paris",
                content_language: "en",
                content_tone: "professional",
                approval_mode: true,
                ui_language: "en",
              },
              providers: [
                {
                  id: "gemini",
                  display_name: "Gemini",
                  default_model: "gemini-2.5-flash",
                  models: [{ id: "gemini-2.5-flash", label: "Gemini 2.5 Flash" }],
                },
              ],
              presets: { countries: [{ country_code: "FR", label: "France" }] },
              feeds: ["https://example.com/feed.xml"],
            },
          }}
        />
      </ToastProvider>,
    );

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save AI Settings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Content Defaults" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Workflow Defaults" })).toBeInTheDocument();
  });
});
