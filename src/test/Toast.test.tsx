import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ToastProvider, useToast } from "../components/Toast";
import React from "react";

function TestConsumer({ onReady }: { onReady: (ctx: { notify: (msg: string, kind?: string) => void }) => void }) {
  const ctx = useToast();
  React.useEffect(() => { onReady(ctx); }, [ctx, onReady]);
  return null;
}

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders and shows a success toast", async () => {
    let toastCtx: { notify: (msg: string, kind?: string) => void };
    render(
      <ToastProvider>
        <TestConsumer onReady={(ctx) => { toastCtx = ctx; }} />
      </ToastProvider>,
    );

    act(() => { toastCtx!.notify("操作成功"); });
    expect(screen.getByText("操作成功")).toBeInTheDocument();
  });

  it("shows error toast with correct styling", async () => {
    let toastCtx: { notify: (msg: string, kind?: string) => void };
    render(
      <ToastProvider>
        <TestConsumer onReady={(ctx) => { toastCtx = ctx; }} />
      </ToastProvider>,
    );

    act(() => { toastCtx!.notify("出错了", "error"); });
    const el = screen.getByText("出错了");
    expect(el).toBeInTheDocument();
    expect(el.closest("div")).toHaveClass("bg-red-600");
  });

  it("removes toast on click", async () => {
    let toastCtx: { notify: (msg: string, kind?: string) => void };
    render(
      <ToastProvider>
        <TestConsumer onReady={(ctx) => { toastCtx = ctx; }} />
      </ToastProvider>,
    );

    act(() => { toastCtx!.notify("可点击关闭"); });
    const el = screen.getByText("可点击关闭");
    fireEvent.click(el);
    expect(screen.queryByText("可点击关闭")).not.toBeInTheDocument();
  });

  it("auto-removes toast after timeout", async () => {
    let toastCtx: { notify: (msg: string, kind?: string) => void };
    render(
      <ToastProvider>
        <TestConsumer onReady={(ctx) => { toastCtx = ctx; }} />
      </ToastProvider>,
    );

    act(() => { toastCtx!.notify("自动消失"); });
    expect(screen.getByText("自动消失")).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(3500); });
    expect(screen.queryByText("自动消失")).not.toBeInTheDocument();
  });

  it("throws when useToast is used outside provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<TestConsumer onReady={() => {}} />)).toThrow(
      "useToast must be used within ToastProvider",
    );
    spy.mockRestore();
  });
});
