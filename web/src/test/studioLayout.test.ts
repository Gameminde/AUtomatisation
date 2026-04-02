import { describe, expect, it } from "vitest";

import { resolveStudioLayoutMode } from "../lib/studioLayout";

describe("resolveStudioLayoutMode", () => {
  it("uses the measured stage width thresholds", () => {
    expect(resolveStudioLayoutMode(1119)).toBe("stacked");
    expect(resolveStudioLayoutMode(1120)).toBe("side-preview");
    expect(resolveStudioLayoutMode(1399)).toBe("side-preview");
    expect(resolveStudioLayoutMode(1400)).toBe("centered");
  });
});
