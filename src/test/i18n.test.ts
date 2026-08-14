import { describe, expect, it } from "vitest";
import i18n from "../i18n";

describe("i18n namespaces", () => {
  it("resolves a translation through a real namespace", async () => {
    await i18n.changeLanguage("en-US");
    const common = i18n.getFixedT("en", "common");

    expect(common("changeLanguage")).toBe("Change language");
    expect(common("switchToLanguage", { language: "МН" })).toBe("Switch to МН");
    expect(i18n.getFixedT("en", "pages")("LLMLabelingPage.inputValuesHint")).toContain("pending review");
    expect(i18n.t("common.changeLanguage")).toBe("common.changeLanguage");

    await i18n.changeLanguage("zh");
  });
});
