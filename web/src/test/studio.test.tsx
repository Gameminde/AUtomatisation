import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BootPayload } from "../lib/boot";
import { createTranslator } from "../lib/i18n";
import { StudioPage } from "../routes/StudioPage";
import { ToastProvider } from "../ui/ToastProvider";

const boot: BootPayload = {
  page: "studio",
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

describe("StudioPage", () => {
  it("renders the preview-first studio experience from bootstrap payload", () => {
    render(
      <ToastProvider>
        <StudioPage
          boot={boot}
          translator={createTranslator({}, "EN")}
          loading={false}
          error={null}
          refresh={async () => null}
          payload={{
            success: true,
            page: "studio",
            shell: {
              setup: { steps: [], all_required_complete: true },
              status: { can_post: false, post_reason: "Connect a Facebook page to publish content." },
            },
            studio: {
              profile: {
                content_language: "en",
                content_tone: "professional",
                niche_preset: "",
              },
              page_context: {},
              presets: { niches: [] },
              status: { can_post: false },
              pages: { pages: [] },
              drafts: [],
              pending: [],
              scheduled: [],
              published: [],
            },
          }}
        />
      </ToastProvider>,
    );

    expect(screen.getByRole("heading", { name: "Design, test, and route every post" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run AI Preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Library 0" })).toBeInTheDocument();
    expect(screen.getByText("Preview unavailable")).toBeInTheDocument();
    expect(screen.getAllByText("No active destination").length).toBeGreaterThan(0);
  });
});
