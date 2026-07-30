import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import type { BridgeProp } from "../lib/types";
import { autoDetectColumn, validateColumnMapping } from "../lib/llm-labeling";
import { LLMLabelingPage } from "../components/pages/LLMLabelingPage";

vi.mock("../lib/ui-components", () => ({
  PathInput: ({
    onChange,
    onFileSelected,
  }: {
    onChange: (value: string) => void;
    onFileSelected?: (value: string) => void;
  }) => (
    <button
      onClick={() => {
        onChange("/tmp/maintenance.xlsx");
        onFileSelected?.("/tmp/maintenance.xlsx");
      }}
    >
      选择测试文件
    </button>
  ),
}));

describe("LLMLabelingPage", () => {
  it("uses safe output column defaults when optional columns are absent", () => {
    expect(autoDetectColumn(["维修内容"], "content_column")).toBe("维修内容");
    expect(autoDetectColumn(["维修内容"], "category_column")).toBe("大类");
    expect(autoDetectColumn(["维修内容"], "minor_column")).toBe("小类");
    expect(autoDetectColumn(["维修内容"], "status_column")).toBe("分类方式");
    expect(validateColumnMapping("维修内容", "大类", "小类", "分类方式")).toBeNull();
    expect(validateColumnMapping("维修内容", "维修内容", "小类", "分类方式")).toContain("冲突");
  });

  it("forwards the selected sheet and keeps execution errors visible", async () => {
    let processParams: Record<string, unknown> | undefined;
    const call: BridgeProp["call"] = async <T,>(
      method: string,
      params?: Record<string, unknown>,
    ): Promise<T> => {
      if (method === "preview_excel_sheets") {
        return { sheets: ["夜班维修"] } as T;
      }
      if (method === "preview_excel_columns") {
        return {
          columns: ["维修内容", "大类", "小类", "分类方式"],
          rows: 1,
          sample: [{
            维修内容: "更换滤芯",
            大类: "其他/待确认",
            小类: "信息不足",
            分类方式: "待确认",
          }],
          value_options: {
            分类方式: [{ value: "待确认", count: 1 }],
          },
        } as T;
      }
      if (method === "process_maintenance_llm") {
        processParams = params;
        throw new Error("接口暂时不可用");
      }
      throw new Error(`unexpected method: ${method}`);
    };

    render(
      <ToastProvider>
        <LLMLabelingPage
          bridge={{ call }}
          progress={null}
          setProgress={vi.fn()}
        />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("选择测试文件"));
    fireEvent.click(await screen.findByText("下一步：列映射"));
    fireEvent.click(screen.getByText("下一步：筛选与导出"));
    fireEvent.click(screen.getByText("开始标注"));

    expect((await screen.findAllByText(/接口暂时不可用/)).length).toBeGreaterThan(0);
    expect(processParams).toMatchObject({ sheet_name: "夜班维修" });
    await waitFor(() => expect(screen.getByText("返回修改")).toBeInTheDocument());
  });
});
