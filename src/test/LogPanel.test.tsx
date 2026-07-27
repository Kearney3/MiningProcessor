import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LogPanel } from "../components/LogPanel";
import type { LogEntry } from "../lib/types";

function makeLog(level: string, message: string, seq?: number): LogEntry {
  return { level, message, timestamp: "10:00:00", seq: seq ?? 0 };
}

describe("LogPanel", () => {
  const onClear = vi.fn();

  beforeEach(() => {
    onClear.mockClear();
  });

  it("shows empty state when no logs", () => {
    render(<LogPanel logs={[]} onClear={onClear} />);
    expect(screen.getByText("等待日志...")).toBeInTheDocument();
  });

  it("renders log entries", () => {
    const logs = [
      makeLog("INFO", "处理开始", 1),
      makeLog("ERROR", "处理失败", 2),
    ];
    render(<LogPanel logs={logs} onClear={onClear} />);
    expect(screen.getByText("处理开始")).toBeInTheDocument();
    expect(screen.getByText("处理失败")).toBeInTheDocument();
  });

  it("displays log count badge", () => {
    const logs = [makeLog("INFO", "msg1", 1), makeLog("INFO", "msg2", 2)];
    render(<LogPanel logs={logs} onClear={onClear} />);
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("filters logs by level", () => {
    const logs = [
      makeLog("INFO", "info-msg", 1),
      makeLog("ERROR", "error-msg", 2),
      makeLog("WARNING", "warn-msg", 3),
    ];
    render(<LogPanel logs={logs} onClear={onClear} />);

    // Filter to ERROR only
    fireEvent.change(screen.getByDisplayValue("INFO"), { target: { value: "ERROR" } });
    expect(screen.getByText("error-msg")).toBeInTheDocument();
    expect(screen.queryByText("info-msg")).not.toBeInTheDocument();
    expect(screen.queryByText("warn-msg")).not.toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // count badge
  });

  it("filters logs by level and above (WARNING shows WARNING + ERROR)", () => {
    const logs = [
      makeLog("INFO", "info-msg", 1),
      makeLog("WARNING", "warn-msg", 2),
      makeLog("ERROR", "error-msg", 3),
    ];
    render(<LogPanel logs={logs} onClear={onClear} />);

    fireEvent.change(screen.getByDisplayValue("INFO"), { target: { value: "WARNING" } });
    expect(screen.getByText("warn-msg")).toBeInTheDocument();
    expect(screen.getByText("error-msg")).toBeInTheDocument();
    expect(screen.queryByText("info-msg")).not.toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("default INFO filter hides DEBUG logs", () => {
    const logs = [
      makeLog("DEBUG", "debug-msg", 1),
      makeLog("INFO", "info-msg", 2),
      makeLog("WARNING", "warn-msg", 3),
      makeLog("ERROR", "error-msg", 4),
    ];
    render(<LogPanel logs={logs} onClear={onClear} />);

    // Default is INFO: shows INFO + WARNING + ERROR, hides DEBUG
    expect(screen.queryByText("debug-msg")).not.toBeInTheDocument();
    expect(screen.getByText("info-msg")).toBeInTheDocument();
    expect(screen.getByText("warn-msg")).toBeInTheDocument();
    expect(screen.getByText("error-msg")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("calls onClear when clear button clicked", () => {
    const logs = [makeLog("INFO", "msg", 1)];
    render(<LogPanel logs={logs} onClear={onClear} />);
    fireEvent.click(screen.getByTitle("清空"));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("pauses following when user scrolls away and resumes on click", () => {
    render(<LogPanel logs={[makeLog("INFO", "msg", 1)]} onClear={onClear} />);
    const region = screen.getByRole("region", { name: "处理日志" });
    Object.defineProperties(region, {
      scrollHeight: { configurable: true, value: 1000 },
      clientHeight: { configurable: true, value: 100 },
      scrollTop: { configurable: true, writable: true, value: 200 },
    });

    fireEvent.scroll(region);
    const followButton = screen.getByText("继续跟随");
    expect(followButton).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(followButton);
    expect(screen.getByText("跟随中")).toHaveAttribute("aria-pressed", "true");
  });

  it("copies logs to clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    const logs = [makeLog("INFO", "copy-test", 1)];
    render(<LogPanel logs={logs} onClear={onClear} />);
    fireEvent.click(screen.getByTitle("复制全部"));
    expect(writeText).toHaveBeenCalledWith("[INFO] copy-test");
  });

  it("copies full diagnostic detail instead of the shortened display message", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const log = { ...makeLog("ERROR", "processing failed", 1), detail: "processing failed\nTraceback detail" };

    render(<LogPanel logs={[log]} onClear={onClear} />);
    fireEvent.click(screen.getByTitle("复制全部"));

    expect(writeText).toHaveBeenCalledWith("[ERROR] processing failed\nTraceback detail");
    expect(screen.queryByText("Traceback detail")).not.toBeInTheDocument();
  });

  it("renders a bounded window while retaining the filtered count", () => {
    const logs = Array.from(
      { length: 1001 },
      (_, index) => makeLog("INFO", `row-${index}`, index + 1),
    );
    render(<LogPanel logs={logs} onClear={onClear} />);

    expect(screen.queryByText("row-0")).not.toBeInTheDocument();
    expect(screen.getByText("row-1000")).toBeInTheDocument();
    expect(screen.getByText("显示最近 1000 条")).toBeInTheDocument();
  });

  it("disables text selection during drag resize", () => {
    render(<LogPanel logs={[]} onClear={onClear} />);

    // 找到拖拽手柄（cursor-row-resize 的 div）
    const handle = document.querySelector(".cursor-row-resize");
    expect(handle).toBeTruthy();

    // 模拟 mousedown 触发拖拽
    fireEvent.mouseDown(handle!);

    // 拖拽期间 document.body.userSelect 应为 "none"
    expect(document.body.style.userSelect).toBe("none");
    expect(document.body.style.cursor).toBe("row-resize");

    // 模拟 mouseup 结束拖拽
    fireEvent.mouseUp(window);

    // 拖拽结束后恢复
    expect(document.body.style.userSelect).toBe("");
    expect(document.body.style.cursor).toBe("");
  });

  it("drag handle has select-none class to prevent text selection", () => {
    render(<LogPanel logs={[]} onClear={onClear} />);
    const handle = document.querySelector(".cursor-row-resize");
    expect(handle).toBeTruthy();
    expect(handle!.className).toContain("select-none");
  });

  it("allows keyboard resizing through the separator", () => {
    render(<LogPanel logs={[]} onClear={onClear} />);
    const handle = screen.getByRole("separator", { name: "调整日志面板高度" });
    expect(handle).toHaveAttribute("aria-valuenow", "180");

    fireEvent.keyDown(handle, { key: "ArrowUp" });

    expect(handle).toHaveAttribute("aria-valuenow", "200");
  });

  it("container adds select-none class during resize", () => {
    const { container } = render(<LogPanel logs={[]} onClear={onClear} />);
    const panel = container.firstElementChild as HTMLElement;
    expect(panel).toBeTruthy();

    // 初始状态不应有 select-none
    expect(panel.className).not.toContain("select-none");

    // 模拟 mousedown 触发拖拽
    const handle = document.querySelector(".cursor-row-resize")!;
    fireEvent.mouseDown(handle);

    // 拖拽期间应有 select-none
    expect(panel.className).toContain("select-none");

    // 模拟 mouseup 结束
    fireEvent.mouseUp(window);
    expect(panel.className).not.toContain("select-none");
  });
});
