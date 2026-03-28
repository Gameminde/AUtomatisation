import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "../routes/DashboardPage";
import { BootPayload } from "../lib/boot";
import { createTranslator } from "../lib/i18n";

const boot: BootPayload = {
  page: "dashboard",
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

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ success: true, events: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
  });

  it("renders the migrated dashboard shell from bootstrap payload", async () => {
    render(
      <DashboardPage
        boot={boot}
        translator={createTranslator({}, "EN")}
        loading={false}
        error={null}
        refresh={async () => null}
        payload={{
          success: true,
          page: "dashboard",
          shell: {
            setup: {
              steps: [
                {
                  id: "connect_page",
                  label: "Connect Facebook page",
                  description: "Required to publish content",
                  action_label: "Open Channels",
                  action_url: "/channels",
                  completed: false,
                  optional: false,
                },
              ],
              all_required_complete: false,
              next_required_step: "connect_page",
            },
            status: {
              can_post: false,
              post_reason: "Connect a Facebook page to publish content.",
              rate_limiter: { remaining: 3, posts_today: 0, daily_limit: 3 },
              ban_detector: { status: "healthy" },
              health: "healthy",
            },
          },
          dashboard: {
            summary: { pending: [], scheduled: [], published: [] },
            health: {
              pipeline: {
                pending_approvals: 0,
                queue_size: 0,
                failed_count: 0,
                published_count_7d: 2,
              },
              cooldown: { reason: "No cooldown active." },
              last_error: { message: "No recent publish failure." },
            },
            events: [],
            pages: {
              pages: [
                { page_id: "page-1", page_name: "Main Page", status: "active", instagram_account_id: "ig-1" },
              ],
            },
          },
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Daily operations cockpit" })).toBeInTheDocument();
    expect(screen.getByText("Connect Facebook page")).toBeInTheDocument();
    expect(screen.getByText("Destination snapshot")).toBeInTheDocument();
    expect(screen.getByText("Main Page")).toBeInTheDocument();

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
  });
});
