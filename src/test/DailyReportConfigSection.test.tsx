import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DailyReportConfigSection } from "../components/user-config/DailyReportConfigSection";
import { ToastProvider } from "../components/Toast";
import type { BridgeProp } from "../lib/types";

describe("DailyReportConfigSection", () => {
  it("validates formulas without saving and shows field errors", async () => {
    const call = vi.fn().mockImplementation((method: string) => {
      if (method === "get_daily_report_config") return Promise.resolve({});
      if (method === "validate_daily_report_config") {
        return Promise.resolve({
          valid: false,
          errors: { 延迟时间: "公式不能为空" },
        });
      }
      return Promise.resolve({});
    });
    const bridge: BridgeProp = { call };

    render(
      <ToastProvider>
        <DailyReportConfigSection bridge={bridge} />
      </ToastProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /日报导出设置/ }));
    fireEvent.click(await screen.findByRole("button", { name: "校验公式" }));

    await waitFor(() => {
      expect(screen.getAllByText("公式不能为空").length).toBeGreaterThan(0);
    });
    expect(call).toHaveBeenCalledWith(
      "validate_daily_report_config",
      expect.objectContaining({ config: expect.objectContaining({ formulas: expect.any(Object) }) }),
    );
    expect(call).not.toHaveBeenCalledWith("save_daily_report_config", expect.anything());
  });
});
