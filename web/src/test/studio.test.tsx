import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BootPayload } from "../lib/boot";
import { createTranslator } from "../lib/i18n";
import { StudioPage } from "../routes/StudioPage";
import { ToastProvider } from "../ui/ToastProvider";

let observedStageWidth = 1440;

class MockResizeObserver {
  private readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    this.callback([{
      target,
      contentRect: {
        width: observedStageWidth,
        height: 0,
        x: 0,
        y: 0,
        top: 0,
        right: observedStageWidth,
        bottom: 0,
        left: 0,
        toJSON: () => ({}),
      } as DOMRectReadOnly,
    } as ResizeObserverEntry], this as unknown as ResizeObserver);
  }

  unobserve() {}

  disconnect() {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  configurable: true,
  writable: true,
  value: MockResizeObserver,
});

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
  it("renders the studio with a brief-only empty preview state and design-only template controls", async () => {
    observedStageWidth = 1440;
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1600 });

    const { container } = render(
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

    const studioPage = container.querySelector(".cf-studio-page");
    await waitFor(() => {
      expect(studioPage).toHaveAttribute("data-studio-layout", "centered");
    });

    expect(screen.getByRole("heading", { name: "Design, test, and route every post" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run AI Preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Library 0" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Facebook preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Expand template" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New Draft" })).toBeInTheDocument();
    expect(screen.getByText("Shape the creative system")).toBeInTheDocument();
    expect(screen.getByText("Preview surface")).toBeInTheDocument();
    expect(screen.getByText("2. Studio draft editor")).toBeInTheDocument();
    expect(screen.getByText("3. Scheduling & finalizing")).toBeInTheDocument();
    expect(screen.getByText("Schedule & publish")).toBeInTheDocument();
    expect(screen.getByText("Quick creative cues")).toBeInTheDocument();
    expect(screen.getAllByText(/No active destination/).length).toBeGreaterThan(0);
    expect(container.querySelector(".cf-studio-dashboard")).toBeInTheDocument();
    expect(container.querySelectorAll(".cf-studio-dashboard-column")).toHaveLength(4);
    expect(container.querySelectorAll(".cf-studio-preview-stack")).toHaveLength(1);
    expect(screen.queryByLabelText("Template title")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Template subtitle")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Preview unavailable")).toBeInTheDocument();
    });
  }, 30000);

  it("uses measured stage width instead of viewport width to choose the layout mode", async () => {
    observedStageWidth = 1260;
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1600 });

    const { container } = render(
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

    const studioPage = container.querySelector(".cf-studio-page");
    await waitFor(() => {
      expect(studioPage).toHaveAttribute("data-studio-layout", "side-preview");
    });
  });

  it("shows upload assets and media controls when a post draft is open", async () => {
    observedStageWidth = 1440;
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1600 });

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
              drafts: [{
                id: "draft-1",
                post_type: "post",
                status: "draft_only",
                platforms: "facebook",
                generated_text: "Body copy",
                hook: "Hook copy",
                hashtags: ["#one"],
                image_path: "",
                target_audience: "EN",
              }],
              pending: [],
              scheduled: [],
              published: [],
            },
          }}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Media assets")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Add main image" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add background" })).toBeInTheDocument();
    expect(screen.getByLabelText("Image width")).toBeInTheDocument();
    expect(screen.getByLabelText("Image height")).toBeInTheDocument();
    expect(screen.getByLabelText("Image clarity")).toBeInTheDocument();
    expect(screen.getByLabelText("Horizontal align")).toBeInTheDocument();
    expect(screen.getByLabelText("Vertical align")).toBeInTheDocument();
    expect(screen.getByLabelText("Zoom")).toBeInTheDocument();
    expect(screen.getByLabelText("Title size")).toBeInTheDocument();
    expect(screen.getByLabelText("Title font")).toBeInTheDocument();
    expect(screen.getByLabelText("Title color")).toBeInTheDocument();
  }, 15000);

  it("shows remove actions when the main image and background already exist", async () => {
    observedStageWidth = 1440;
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1600 });

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
                template_defaults: {
                  backgroundImagePath: "/generated_images/background.png",
                },
              },
              page_context: {},
              presets: { niches: [] },
              status: { can_post: false },
              pages: { pages: [] },
              drafts: [{
                id: "draft-1",
                post_type: "post",
                status: "draft_only",
                platforms: "facebook",
                generated_text: "Body copy",
                hook: "Hook copy",
                hashtags: ["#one"],
                image_path: "downloaded_images/main.png",
                target_audience: "EN",
              }],
              pending: [],
              scheduled: [],
              published: [],
            },
          }}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(2);
    });
  }, 15000);
});
