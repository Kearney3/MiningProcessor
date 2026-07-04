import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useLastDirectory } from "../hooks/useLastDirectory";

function makeBridge(savedPath: string = "") {
  return {
    call: vi.fn().mockImplementation((method: string) => {
      if (method === "get_last_directory") return Promise.resolve({ path: savedPath });
      if (method === "save_last_directory") return Promise.resolve({ ok: true });
      return Promise.resolve({});
    }),
  };
}

describe("useLastDirectory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads saved directory on mount", async () => {
    const bridge = makeBridge("/Users/test/Documents");
    const { result } = renderHook(() => useLastDirectory(bridge));

    expect(result.current.initialDir).toBe("");
    await waitFor(() => {
      expect(result.current.initialDir).toBe("/Users/test/Documents");
    });
    expect(bridge.call).toHaveBeenCalledWith("get_last_directory", { key: "last_directory" });
  });

  it("defaults to empty when no saved directory", async () => {
    const bridge = makeBridge("");
    const { result } = renderHook(() => useLastDirectory(bridge));

    await waitFor(() => {
      expect(bridge.call).toHaveBeenCalled();
    });
    expect(result.current.initialDir).toBe("");
  });

  it("uses custom config key", async () => {
    const bridge = makeBridge("/custom/path");
    renderHook(() => useLastDirectory(bridge, "sync_last_input_dir"));

    await waitFor(() => {
      expect(bridge.call).toHaveBeenCalledWith("get_last_directory", { key: "sync_last_input_dir" });
    });
  });

  it("saveDir extracts parent directory and persists", async () => {
    const bridge = makeBridge();
    const { result } = renderHook(() => useLastDirectory(bridge));

    await waitFor(() => {
      expect(bridge.call).toHaveBeenCalled();
    });

    act(() => {
      result.current.saveDir("/Users/test/Documents/file.xlsx");
    });

    expect(bridge.call).toHaveBeenCalledWith("save_last_directory", {
      key: "last_directory",
      path: "/Users/test/Documents",
    });
  });

  it("saveDir updates initialDir reactively", async () => {
    const bridge = makeBridge();
    const { result } = renderHook(() => useLastDirectory(bridge));

    await waitFor(() => {
      expect(bridge.call).toHaveBeenCalled();
    });

    act(() => {
      result.current.saveDir("/new/path/file.xlsx");
    });

    expect(result.current.initialDir).toBe("/new/path");
  });

  it("handles bridge errors gracefully", async () => {
    const bridge = { call: vi.fn().mockRejectedValue(new Error("bridge error")) };
    const { result } = renderHook(() => useLastDirectory(bridge));

    await waitFor(() => {
      expect(bridge.call).toHaveBeenCalled();
    });
    expect(result.current.initialDir).toBe("");
  });
});
