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
    fireEvent.change(screen.getByDisplayValue("全部"), { target: { value: "ERROR" } });
    expect(screen.getByText("error-msg")).toBeInTheDocument();
    expect(screen.queryByText("info-msg")).not.toBeInTheDocument();
    expect(screen.queryByText("warn-msg")).not.toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // count badge
  });

  it("calls onClear when clear button clicked", () => {
    const logs = [makeLog("INFO", "msg", 1)];
    render(<LogPanel logs={logs} onClear={onClear} />);
    fireEvent.click(screen.getByTitle("清空"));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("toggles auto-scroll", () => {
    render(<LogPanel logs={[]} onClear={onClear} />);
    const autoBtn = screen.getByText("Auto");
    expect(autoBtn).toHaveClass("text-blue-600");
    fireEvent.click(autoBtn);
    expect(autoBtn).toHaveClass("text-slate-400");
  });

  it("copies logs to clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    const logs = [makeLog("INFO", "copy-test", 1)];
    render(<LogPanel logs={logs} onClear={onClear} />);
    fireEvent.click(screen.getByTitle("复制全部"));
    expect(writeText).toHaveBeenCalledWith("[INFO] copy-test");
  });
});
