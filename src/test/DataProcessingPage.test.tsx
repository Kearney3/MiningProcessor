import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DataProcessingPage } from "../components/pages/DataProcessingPage";
import { ToastProvider } from "../components/Toast";
import type { BridgeProp } from "../lib/types";


function renderPage(call: BridgeProp["call"]) {
  const bridge: BridgeProp = { call };
  render(
    <ToastProvider>
      <DataProcessingPage bridge={bridge} />
    </ToastProvider>,
  );
}


describe("DataProcessingPage maintenance ML switch", () => {
  it("defaults to enabled and forwards a disabled selection", async () => {
    const call = vi.fn().mockImplementation((method: string) => {
      if (method === "get_last_directory") return Promise.resolve({ path: "" });
      if (method === "process_maintenance") {
        return Promise.resolve({ output_file: "/tmp/维修记录统计.xlsx" });
      }
      return Promise.resolve({});
    });
    renderPage(call as BridgeProp["call"]);

    const heading = screen.getByText("维修记录处理");
    const card = heading.closest(".bg-white");
    expect(card).not.toBeNull();
    const controls = within(card as HTMLElement);
    const mlSwitch = controls.getByRole("switch", {
      name: "启用机器学习辅助识别",
    });
    expect(mlSwitch).toHaveAttribute("aria-checked", "true");

    fireEvent.click(mlSwitch);
    fireEvent.change(
      controls.getByPlaceholderText("选择出勤统计表文件或文件夹"),
      { target: { value: "/tmp/input.xlsx" } },
    );
    fireEvent.click(controls.getByText("开始处理"));

    await waitFor(() => {
      expect(call).toHaveBeenCalledWith(
        "process_maintenance",
        expect.objectContaining({ use_ml_fallback: false }),
      );
    });
  });
});
