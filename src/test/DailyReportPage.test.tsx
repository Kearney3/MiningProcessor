import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DailyReportPage } from "../components/pages/DailyReportPage";
import { ToastProvider } from "../components/Toast";
import type { BridgeProp } from "../lib/types";

describe("DailyReportPage", () => {
  it("sends runtime output options and detail-sheet selection", async () => {
    const call = vi.fn().mockImplementation((method: string) => {
      if (method === "get_last_directory") return Promise.resolve({ path: "" });
      if (method === "daily_report_export") {
        return Promise.resolve({ output_file: "/tmp/每日.xlsx", rows: 1, warnings: [], detail_sheets: ["工时统计"] });
      }
      return Promise.resolve({});
    });
    const bridge: BridgeProp = { call };

    render(
      <ToastProvider>
        <DailyReportPage bridge={bridge} />
      </ToastProvider>,
    );

    fireEvent.change(screen.getByPlaceholderText("选择数据目录"), { target: { value: "/tmp/report" } });
    fireEvent.click(screen.getByRole("switch", { name: "输出原始设备名称" }));
    fireEvent.click(screen.getByRole("switch", { name: "输出分项表格" }));
    fireEvent.click(screen.getByText("导出每日报表"));

    await waitFor(() => {
      expect(call).toHaveBeenCalledWith(
        "daily_report_export",
        expect.objectContaining({
          include_detail_sheets: true,
          config: expect.objectContaining({
            include_raw_equipment_name: false,
            include_raw_equipment_code: true,
            include_raw_company_name: true,
          }),
        }),
      );
    });
  });
});
