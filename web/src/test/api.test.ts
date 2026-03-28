import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiCall, apiFetch } from "../lib/api";
import * as auth from "../lib/auth";

describe("api helpers", () => {
  beforeEach(() => {
    document.head.innerHTML = '<meta name="csrf-token" content="csrf-123">';
    vi.restoreAllMocks();
  });

  it("sends csrf and same-origin headers", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);

    await apiFetch("/api/bootstrap?page=dashboard");

    const request = mockFetch.mock.calls[0]?.[1] as RequestInit;
    const headers = request.headers as Headers;
    expect(request.credentials).toBe("same-origin");
    expect(headers.get("X-CSRFToken")).toBe("csrf-123");
    expect(headers.get("X-Requested-With")).toBe("XMLHttpRequest");
  });

  it("throws the backend error payload message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "nope" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      }),
    ));

    await expect(apiCall("/api/test", "POST", {})).rejects.toThrow("nope");
  });

  it("redirects to login on 401", async () => {
    const redirectSpy = vi.spyOn(auth, "redirectToLogin").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "unauthorized" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    ));

    await expect(apiCall("/api/private")).rejects.toThrow("unauthorized");
    expect(redirectSpy).toHaveBeenCalledOnce();
  });
});
