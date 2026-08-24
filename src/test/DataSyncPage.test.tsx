import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DataSyncPage } from "../components/pages/DataSyncPage";
import type { BridgeProp } from "../lib/types";
import { ToastProvider } from "../components/Toast";
import { save } from "@tauri-apps/plugin-dialog";

function makeBridge(overrides?: Partial<BridgeProp>): BridgeProp {
  return {
    call: vi.fn().mockResolvedValue({ path: "", exists: false }),
    ...overrides,
  };
}

function renderPage(bridge?: BridgeProp) {
  const b = bridge ?? makeBridge();
  return render(
    <ToastProvider>
      <DataSyncPage bridge={b} />
    </ToastProvider>,
  );
}

describe("DataSyncPage - Export Warnings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders export button when warnings exist", async () => {
    const bridge = makeBridge({
      call: vi.fn().mockImplementation((method: string) => {
        if (method === "get_last_directory") return Promise.resolve({ path: "" });
        if (method === "sync_minebase") {
          return Promise.resolve({
            results: {
              fuel: {
                success: 1, skipped: 0, failed: 0,
                warnings: [
                  { row: 2, field: "sourceEquipmentName", value: "旧设备", message: "未匹配" },
                ],
              },
            },
          });
        }
        return Promise.resolve({});
      }),
    });

    renderPage(bridge);

    // 填入目录路径触发同步
    const input = screen.getByPlaceholderText("选择包含已处理数据的文件夹");
    fireEvent.change(input, { target: { value: "/tmp/test" } });

    // 点击同步按钮
    const syncBtn = screen.getByText("开始同步");
    fireEvent.click(syncBtn);

    // 等待同步完成，导出按钮应出现
    const exportBtn = await screen.findByText("导出 Excel");
    expect(exportBtn).toBeInTheDocument();
  });

  it("calls save dialog when export button is clicked", async () => {
    const mockSave = vi.mocked(save);
    mockSave.mockResolvedValue("/tmp/custom_warnings.xlsx");

    const mockCall = vi.fn().mockImplementation((method: string) => {
      if (method === "get_last_directory") return Promise.resolve({ path: "" });
      if (method === "sync_minebase") {
        return Promise.resolve({
          results: {
            fuel: {
              success: 1, skipped: 0, failed: 0,
              warnings: [
                { row: 2, field: "sourceEquipmentName", value: "旧设备", message: "未匹配" },
              ],
            },
          },
        });
      }
      if (method === "export_sync_warnings") {
        return Promise.resolve({ output_file: "/tmp/custom_warnings.xlsx" });
      }
      return Promise.resolve({});
    });

    const bridge = makeBridge({ call: mockCall });
    renderPage(bridge);

    // 填入目录
    const input = screen.getByPlaceholderText("选择包含已处理数据的文件夹");
    fireEvent.change(input, { target: { value: "/tmp/test" } });

    // 点击同步
    fireEvent.click(screen.getByText("开始同步"));

    // 等待导出按钮出现
    const exportBtn = await screen.findByText("导出 Excel");
    fireEvent.click(exportBtn);

    // 应调用 save 对话框
    await vi.waitFor(() => {
      expect(mockSave).toHaveBeenCalled();
    });

    // 应调用 export_sync_warnings RPC，传入自定义路径
    await vi.waitFor(() => {
      expect(mockCall).toHaveBeenCalledWith("export_sync_warnings", expect.objectContaining({
        output_path: "/tmp/custom_warnings.xlsx",
      }));
    });
  });

  it("does not export when save dialog is cancelled", async () => {
    const mockSave = vi.mocked(save);
    mockSave.mockResolvedValue(null); // 用户取消

    const mockCall = vi.fn().mockImplementation((method: string) => {
      if (method === "get_last_directory") return Promise.resolve({ path: "" });
      if (method === "sync_minebase") {
        return Promise.resolve({
          results: {
            fuel: {
              success: 1, skipped: 0, failed: 0,
              warnings: [
                { row: 2, field: "sourceEquipmentName", value: "旧设备", message: "未匹配" },
              ],
            },
          },
        });
      }
      return Promise.resolve({});
    });

    const bridge = makeBridge({ call: mockCall });
    renderPage(bridge);

    const input = screen.getByPlaceholderText("选择包含已处理数据的文件夹");
    fireEvent.change(input, { target: { value: "/tmp/test" } });
    fireEvent.click(screen.getByText("开始同步"));

    const exportBtn = await screen.findByText("导出 Excel");
    fireEvent.click(exportBtn);

    await vi.waitFor(() => {
      expect(mockSave).toHaveBeenCalled();
    });

    // 取消后不应调用 export_sync_warnings
    expect(mockCall).not.toHaveBeenCalledWith("export_sync_warnings", expect.anything());
  });

  it("shows empty placeholder for null/empty values in warnings table", async () => {
    const bridge = makeBridge({
      call: vi.fn().mockImplementation((method: string) => {
        if (method === "get_last_directory") return Promise.resolve({ path: "" });
        if (method === "sync_minebase") {
          return Promise.resolve({
            results: {
              fuel: {
                success: 0, skipped: 0, failed: 0,
                warnings: [
                  { row: 1, field: "sourceTruckName", value: "", message: "缺少矿卡" },
                  { row: 2, field: "sourceEquipmentName", value: null, message: "缺少设备" },
                ],
              },
            },
          });
        }
        return Promise.resolve({});
      }),
    });

    renderPage(bridge);

    const input = screen.getByPlaceholderText("选择包含已处理数据的文件夹");
    fireEvent.change(input, { target: { value: "/tmp/test" } });
    fireEvent.click(screen.getByText("开始同步"));

    // 等待异常行表格渲染
    await screen.findByText("异常行");

    // 空值和 null 值都应显示为 "（空）"
    const emptyCells = screen.getAllByText("（空）");
    expect(emptyCells.length).toBe(2);
  });

  it("renders anomaly locator fields and exports anomaly results", async () => {
    const mockSave = vi.mocked(save);
    mockSave.mockResolvedValue("/tmp/anomalies.xlsx");
    const mockCall = vi.fn().mockImplementation((method: string) => {
      if (method === "get_last_directory") return Promise.resolve({ path: "" });
      if (method === "sync_minebase") {
        return Promise.resolve({
          results: {
            fuel: {
              success: 0,
              skipped: 0,
              failed: 0,
              anomalies: [{
                数据类型: "油耗信息",
                相关字段: "油品消耗",
                异常值: 50001,
                异常值原因: "超过上限 50000",
                行号: 8,
                源表: "油耗信息",
                源行号: 22,
                检测方法: "threshold",
              }],
            },
          },
        });
      }
      if (method === "export_sync_anomalies") {
        return Promise.resolve({ output_file: "/tmp/anomalies.xlsx" });
      }
      return Promise.resolve({});
    });

    renderPage(makeBridge({ call: mockCall }));
    const input = screen.getByPlaceholderText("选择包含已处理数据的文件夹");
    fireEvent.change(input, { target: { value: "/tmp/test" } });
    fireEvent.click(screen.getByText("开始同步"));

    expect(await screen.findByText("threshold")).toBeInTheDocument();
    expect(screen.getByText("源表")).toBeInTheDocument();
    expect(screen.getByText("源行号")).toBeInTheDocument();
    fireEvent.click(screen.getByText("导出异常值结果"));

    await vi.waitFor(() => {
      expect(mockCall).toHaveBeenCalledWith("export_sync_anomalies", expect.objectContaining({
        output_path: "/tmp/anomalies.xlsx",
        records: expect.arrayContaining([
          expect.objectContaining({ 相关字段: "油品消耗", 行号: 8, 检测方法: "threshold" }),
        ]),
      }));
    });
  });
});
