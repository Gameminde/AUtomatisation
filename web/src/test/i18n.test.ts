import { describe, expect, it } from "vitest";

import { createTranslator } from "../lib/i18n";

describe("i18n helper", () => {
  it("translates catalog keys and parameters", () => {
    const translator = createTranslator(
      {
        FR: {
          Hello: "Bonjour",
          "Count {value}": "Compte {value}",
        },
      },
      "FR",
    );

    expect(translator.tr("Hello")).toBe("Bonjour");
    expect(translator.tr("Count {value}", { value: 3 })).toBe("Compte 3");
  });

  it("falls back to the source key when missing", () => {
    const translator = createTranslator({}, "EN");
    expect(translator.tr("Missing key")).toBe("Missing key");
  });
});
