import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePythonBridge } from "../hooks/usePythonBridge";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const mockInvoke = vi.mocked(invoke);
const mockListen = vi.mocked(listen);

describe("usePythonBridge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    mockInvoke.mockResolvedValue({ pong: true, pid: 1234, version: "1.2.0" });
    mockListen.mockResolvedValue(() => {});
  });

  it("initializes with connecting status", () => {
    const { result } = renderHook(() => usePythonBridge());
    expect(result.current.connectionStatus).toBe("connecting");
    expect(result.current.isConnected).toBe(false);
  });

  it("connects on mount via ping", async () => {
    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.isConnected).toBe(true);
    expect(result.current.connectionStatus).toBe("connected");
  });

  it("provides call function", async () => {
    mockInvoke.mockResolvedValue({ pong: true, pid: 1, version: "1.2.0" });

    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // Override for the next call
    mockInvoke.mockResolvedValueOnce({ output_file: "/tmp/out.xlsx" });
    const res = await result.current.call("process_fuel", { path: "/test.xlsx" });
    expect(res).toEqual({ output_file: "/tmp/out.xlsx" });
    expect(mockInvoke).toHaveBeenCalledWith("invoke_python", {
      method: "process_fuel",
      params: { path: "/test.xlsx" },
    });
  });

  it("provides cancel function", async () => {
    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await result.current.cancel();
    expect(mockInvoke).toHaveBeenCalledWith("cancel_task");
  });

  it("clears logs", async () => {
    // Simulate a log event
    let logHandler: (event: { payload: { event: string; data: Record<string, unknown> } }) => void;
    mockListen.mockImplementation(async (_event, handler) => {
      logHandler = handler as typeof logHandler;
      return () => {};
    });

    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // Simulate receiving a log
    act(() => {
      logHandler!({
        payload: { event: "log", data: { level: "INFO", message: "test log" } },
      });
    });
    expect(result.current.logs.length).toBe(0);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(result.current.logs.length).toBe(1);

    act(() => {
      result.current.clearLogs();
    });
    expect(result.current.logs.length).toBe(0);
  });

  it("clearing also discards logs waiting in the batch buffer", async () => {
    let logHandler: (event: { payload: { event: string; data: Record<string, unknown> } }) => void;
    mockListen.mockImplementation(async (_event, handler) => {
      logHandler = handler as typeof logHandler;
      return () => {};
    });
    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    act(() => {
      logHandler!({
        payload: { event: "log", data: { level: "INFO", message: "pending" } },
      });
      result.current.clearLogs();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.logs).toEqual([]);
  });

  it("consumes Rust log batches in one state flush with stable sequences", async () => {
    let logHandler: (event: { payload: { event: string; data: Record<string, unknown> } }) => void;
    mockListen.mockImplementation(async (_event, handler) => {
      logHandler = handler as typeof logHandler;
      return () => {};
    });
    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    act(() => {
      logHandler!({
        payload: {
          event: "log_batch",
          data: {
            entries: [
              { event: "log", data: { seq: 1, level: "INFO", message: "first" } },
              { event: "log", data: { seq: 2, level: "ERROR", message: "second" } },
            ],
          },
        },
      });
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    expect(result.current.logs.map((entry) => entry.message)).toEqual(["first", "second"]);
    expect(result.current.logs.map((entry) => entry.seq)).toEqual([1, 2]);
  });

  it("accepts only structurally valid progress events", async () => {
    let eventHandler: (event: { payload: { event: string; data: Record<string, unknown> } }) => void;
    mockListen.mockImplementation(async (_event, handler) => {
      eventHandler = handler as typeof eventHandler;
      return () => {};
    });

    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    act(() => {
      eventHandler!({
        payload: {
          event: "progress",
          data: { stage: "running", percent: "50", current: 1, total: 2, detail: "invalid" },
        },
      });
    });
    expect(result.current.progress).toBeNull();

    act(() => {
      eventHandler!({
        payload: {
          event: "progress",
          data: { stage: "running", percent: 50, current: 1, total: 2, detail: "valid" },
        },
      });
    });
    expect(result.current.progress).toMatchObject({
      stage: "running",
      percent: 50,
      current: 1,
      total: 2,
      detail: "valid",
    });
  });

  it("bounds history while preserving warnings during a log burst", async () => {
    let logHandler: (event: { payload: { event: string; data: Record<string, unknown> } }) => void;
    mockListen.mockImplementation(async (_event, handler) => {
      logHandler = handler as typeof logHandler;
      return () => {};
    });
    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const entries = [
      { event: "log", data: { seq: 1, level: "WARNING", message: "keep-warning" } },
      ...Array.from({ length: 5000 }, (_, index) => ({
        event: "log",
        data: { seq: index + 2, level: "INFO", message: `regular-${index}` },
      })),
    ];

    act(() => {
      logHandler!({
        payload: { event: "log_batch", data: { entries } },
      });
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    expect(result.current.logs).toHaveLength(5000);
    expect(result.current.logs.some((entry) => entry.message === "keep-warning")).toBe(true);
    expect(result.current.logs.some((entry) => entry.message === "regular-0")).toBe(false);
  });

  it("handles ping failure and marks disconnected after max retries", async () => {
    mockInvoke.mockRejectedValue(new Error("connection refused"));
    const { result } = renderHook(() => usePythonBridge());
    // First ping fails (failCount = 1, still "connecting")
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.isConnected).toBe(false);

    // Trigger second heartbeat failure (failCount = 2 → disconnected)
    await act(async () => {
      vi.advanceTimersByTime(30_000);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.connectionStatus).toBe("disconnected");
  });

  it("handles connection event from Rust", async () => {
    let connHandler: (event: { payload: { event: string; data: Record<string, unknown> } }) => void;
    mockListen.mockImplementation(async (_event, handler) => {
      connHandler = handler as typeof connHandler;
      return () => {};
    });

    const { result } = renderHook(() => usePythonBridge());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    act(() => {
      connHandler!({
        payload: {
          event: "connection",
          data: { status: "connected", mode: "sidecar", pid: 5678 },
        },
      });
    });
    expect(result.current.connectionStatus).toBe("connected");
    expect(result.current.bridgeInfo?.mode).toBe("sidecar");
    expect(result.current.bridgeInfo?.pid).toBe(5678);
  });
});
