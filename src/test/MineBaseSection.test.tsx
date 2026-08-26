import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MineBaseSection } from "../components/user-config/MineBaseSection";
import { ToastProvider } from "../components/Toast";
import type { BridgeProp } from "../lib/types";

describe("MineBaseSection", () => {
  it("adds a connection profile and preserves masked passwords when saving", async () => {
    const initialConfig = {
      active_profile_id: "production-admin",
      profiles: [{
        id: "production-admin",
        name: "生产管理员",
        mode: "api",
        api: {
          url: "https://minebase.example.com",
          username: "admin",
          password: "__keyring__",
        },
        database: {
          host: "localhost",
          port: 5432,
          database: "minebase",
          user: "postgres",
          password: "",
        },
      }],
    };
    const call = vi.fn().mockImplementation((method: string) => {
      if (method === "get_config") return Promise.resolve(initialConfig);
      return Promise.resolve({});
    });
    const bridge: BridgeProp = { call };

    render(
      <ToastProvider>
        <MineBaseSection bridge={bridge} />
      </ToastProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /MineBase 连接配置/ }));
    const profileSelect = await screen.findByLabelText("已保存的连接");
    expect(profileSelect).toHaveValue("production-admin");
    expect(screen.getByDisplayValue("********")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "新增连接" }));
    expect(profileSelect.querySelectorAll("option")).toHaveLength(2);

    fireEvent.change(screen.getByLabelText("连接名称"), { target: { value: "生产只读" } });
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "reader" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(call).toHaveBeenCalledWith(
        "save_minebase_config",
        expect.objectContaining({
          config: expect.objectContaining({
            profiles: expect.arrayContaining([
              expect.objectContaining({
                id: "production-admin",
                api: expect.objectContaining({ password: "__keyring__" }),
              }),
              expect.objectContaining({
                name: "生产只读",
                api: expect.objectContaining({ username: "reader" }),
              }),
            ]),
          }),
        }),
      );
    });
  });
});
