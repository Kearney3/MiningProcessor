import { fireEvent, render, screen, waitFor, within, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import App from "../App";

vi.mock("@tauri-apps/api/app", () => ({
  getVersion: vi.fn(() => Promise.resolve("3.0.1")),
}));

const mockInvoke = vi.mocked(invoke);

describe("App task navigation", () => {
  it("keeps the active task and its form state when navigating away and back", async () => {
    let finishTask!: (result: unknown) => void;
    const pendingTask = new Promise<unknown>((resolve) => { finishTask = resolve; });
    mockInvoke.mockImplementation(async (command, args) => {
      if (command !== "invoke_python") return {};
      const method = (args as { method?: string }).method;
      if (method === "ping") return { pong: true, pid: 1234, version: "1.2.0" };
      if (method === "get_last_directory") return { path: "" };
      if (method === "process_fuel") return pendingTask;
      return {};
    });

    render(<App />);

    const fuelHeading = await screen.findByText("油耗处理");
    const fuelCard = fuelHeading.closest(".bg-white");
    expect(fuelCard).not.toBeNull();
    const fuelControls = within(fuelCard as HTMLElement);
    fireEvent.change(fuelControls.getByPlaceholderText("选择 Excel 文件"), {
      target: { value: "/tmp/fuel.xlsx" },
    });
    fireEvent.click(fuelControls.getByText("开始处理"));

    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalledWith("invoke_python", expect.objectContaining({
        method: "process_fuel",
        params: expect.objectContaining({ path: "/tmp/fuel.xlsx" }),
      }));
    });

    fireEvent.click(screen.getByRole("button", { name: "批量处理" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "批量处理" })).toHaveAttribute("aria-current", "page");
    });
    expect(screen.getByLabelText("正在处理")).toHaveTextContent("油耗处理");

    fireEvent.click(screen.getByRole("button", { name: "数据处理" }));
    expect(fuelControls.getByPlaceholderText("选择 Excel 文件")).toHaveValue("/tmp/fuel.xlsx");
    expect(fuelControls.getByText("处理中...")).toBeInTheDocument();

    await act(async () => {
      finishTask({ output_file: "/tmp/fuel-result.xlsx", anomalies: [] });
      await pendingTask;
    });

    await waitFor(() => expect(screen.getByLabelText("正在处理")).toHaveTextContent("已完成"));
    expect(fuelControls.getByText("输出: /tmp/fuel-result.xlsx")).toBeInTheDocument();
  });
});
