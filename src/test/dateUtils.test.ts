import { describe, expect, it, vi } from "vitest";
import {
  formatLocalDate,
  localDateTimeISO,
  localTodayString,
  localYesterdayString,
  parseLocalDate,
} from "../lib/dateUtils";

describe("dateUtils", () => {
  it("uses the local calendar date around midnight", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 7, 12, 1, 30, 0));

    expect(localTodayString()).toBe("2026-08-12");
    expect(localYesterdayString()).toBe("2026-08-11");

    vi.useRealTimers();
  });

  it("round-trips business dates without UTC conversion", () => {
    expect(formatLocalDate(parseLocalDate("2026-08-12"))).toBe("2026-08-12");
  });

  it("formats fallback timestamps with a local offset", () => {
    const value = new Date(2026, 7, 12, 1, 2, 3, 4);

    expect(localDateTimeISO(value)).toMatch(
      /^2026-08-12T01:02:03\.004[+-]\d{2}:\d{2}$/,
    );
  });
});
