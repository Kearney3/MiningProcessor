import { useCallback, useEffect, useState } from "react";

/** Bridge shape required by this hook (subset of usePythonBridge) */
type BridgeCaller = {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
};

interface UseLastDirectoryReturn {
  /** 上次使用的目录路径，加载完成后可用 */
  initialDir: string;
  /** 保存新的目录路径到 config.user.json */
  saveDir: (dirPath: string) => void;
}

/**
 * 目录路径持久化 hook
 *
 * 统一从 config.user.json 加载/保存文件选择器的上次使用目录，
 * 供 Tauri 前端所有页面共用，消除 localStorage 孤岛。
 *
 * @param bridge usePythonBridge 返回的 bridge 对象
 * @param configKey config.user.json 中的 key（如 "last_directory", "sync_last_input_dir" 等）
 */
export function useLastDirectory(
  bridge: BridgeCaller,
  configKey: string = "last_directory",
): UseLastDirectoryReturn {
  const [initialDir, setInitialDir] = useState("");

  // 启动时加载上次目录
  useEffect(() => {
    bridge
      .call<{ path: string }>("get_last_directory", { key: configKey })
      .then((res) => {
        if (res.path) setInitialDir(res.path);
      })
      .catch(() => {});
  }, [bridge, configKey]);

  // 保存目录：取文件路径的父目录
  const saveDir = useCallback(
    (filePath: string) => {
      const dir = filePath.includes("/") || filePath.includes("\\")
        ? filePath.replace(/[\\/][^\\/]*$/, "")
        : filePath;
      if (dir) {
        setInitialDir(dir);
        bridge
          .call("save_last_directory", { key: configKey, path: dir })
          .catch(() => {});
      }
    },
    [bridge, configKey],
  );

  return { initialDir, saveDir };
}
