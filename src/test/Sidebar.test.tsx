import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Sidebar } from "../components/Sidebar";
import type { PageId } from "../lib/types";

describe("Sidebar", () => {
  const onNavigate = vi.fn();

  it("renders all navigation items", () => {
    render(<Sidebar currentPage="data-processing" onNavigate={onNavigate} />);
    expect(screen.getByText("数据处理")).toBeInTheDocument();
    expect(screen.getByText("批量处理")).toBeInTheDocument();
    expect(screen.getByText("数据同步")).toBeInTheDocument();
    expect(screen.getByText("台账匹配")).toBeInTheDocument();
    expect(screen.getByText("设备台账")).toBeInTheDocument();
    expect(screen.getByText("油品台账")).toBeInTheDocument();
    expect(screen.getByText("装载量配置")).toBeInTheDocument();
    expect(screen.getByText("用户配置")).toBeInTheDocument();
  });

  it("renders group headers", () => {
    render(<Sidebar currentPage="data-processing" onNavigate={onNavigate} />);
    expect(screen.getByText("工作区")).toBeInTheDocument();
    expect(screen.getByText("管理")).toBeInTheDocument();
  });

  it("highlights the current page", () => {
    render(<Sidebar currentPage="batch-processing" onNavigate={onNavigate} />);
    const batchBtn = screen.getByText("批量处理");
    expect(batchBtn.closest("button")).toHaveClass("bg-blue-50", "text-blue-700");
    const dataBtn = screen.getByText("数据处理");
    expect(dataBtn.closest("button")).not.toHaveClass("bg-blue-50");
  });

  it("calls onNavigate when item clicked", () => {
    render(<Sidebar currentPage="data-processing" onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("油品台账"));
    expect(onNavigate).toHaveBeenCalledWith("oil-ledger");
  });

  it("navigates to all pages", () => {
    render(<Sidebar currentPage="data-processing" onNavigate={onNavigate} />);
    const pages: PageId[] = [
      "data-processing", "batch-processing", "data-sync", "ledger-match",
      "equipment-ledger", "oil-ledger", "load-config", "user-config",
    ];
    const labels = ["数据处理", "批量处理", "数据同步", "台账匹配", "设备台账", "油品台账", "装载量配置", "用户配置"];
    labels.forEach((label, i) => {
      fireEvent.click(screen.getByText(label));
      expect(onNavigate).toHaveBeenCalledWith(pages[i]);
    });
  });
});
