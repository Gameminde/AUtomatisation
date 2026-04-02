import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BootPayload } from "../lib/boot";
import { createTranslator } from "../lib/i18n";
import { DiagnosticsPage } from "../routes/DiagnosticsPage";
import { ToastProvider } from "../ui/ToastProvider";

const boot: BootPayload = {
  page: "diagnostics",
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

describe("DiagnosticsPage", () => {
  it("renders health summaries and service checks from bootstrap payload", () => {
    render(
      <ToastProvider>
        <DiagnosticsPage
          boot={boot}
          translator={createTranslator({}, "EN")}
          loading={false}
          error={null}
          refresh={async () => null}
          payload={{
            success: true,
            page: "diagnostics",
            shell: {},
            diagnostics: {
              health: {
                page: { connected: true, page_name: "Main Page" },
                cooldown: { active: false, reason: "Publishing is ready." },
                pipeline: { pending_approvals: 2, failed_count: 1 },
                tokens: { facebook_page_name: "Main Page", instagram_connected: true, ai: true, pexels: false },
                last_error: { status: "failed", message: "Retry later", retry_count: 1, at: "2026-03-28T10:00:00Z" },
              },
              events: [{ type: "publish", message: "Post published", at: "2026-03-28T10:00:00Z" }],
            },
          }}
        />
      </ToastProvider>,
    );

    expect(screen.getByRole("heading", { name: "Diagnostics" })).toBeInTheDocument();
    expect(screen.getAllByText("Main Page")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Test facebook Run a live check against the current workspace state." })).toBeInTheDocument();
    expect(screen.getByText("Post published")).toBeInTheDocument();
  }, 15000);
});
