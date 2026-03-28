import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BootPayload } from "../lib/boot";
import { createTranslator } from "../lib/i18n";
import { ChannelsPage } from "../routes/ChannelsPage";
import { ToastProvider } from "../ui/ToastProvider";

const boot: BootPayload = {
  page: "channels",
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

describe("ChannelsPage", () => {
  it("renders connected destinations from bootstrap payload", () => {
    render(
      <ToastProvider>
        <ChannelsPage
          boot={boot}
          translator={createTranslator({}, "EN")}
          loading={false}
          error={null}
          refresh={async () => null}
          payload={{
            success: true,
            page: "channels",
            shell: {},
            channels: {
              pages: {
                pages: [
                  {
                    page_id: "page-1",
                    page_name: "Main Page",
                    instagram_account_id: "ig-1",
                    posts_per_day: 3,
                    posting_times: "08:00,18:00",
                    language: "en",
                    status: "active",
                  },
                ],
              },
              facebook: { connected: true },
              instagram: { connected: true },
              telegram_code: { code: "ABC123", deep_link: "https://t.me/example" },
              telegram_status: { connected: false },
              telegram_summary: { enabled: false, daily_summary_time: "08:00" },
            },
          }}
        />
      </ToastProvider>,
    );

    expect(screen.getByRole("heading", { name: "Channels" })).toBeInTheDocument();
    expect(screen.getAllByText("Main Page")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Save destination defaults" })).toBeInTheDocument();
    expect(screen.getByText("ABC123")).toBeInTheDocument();
  });
});
