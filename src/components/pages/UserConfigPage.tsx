import type { BridgeProp } from "../../lib/types";
import {
  LLMConfigSection,
  MineBaseSection,
  FileKeywordsSection,
  HeaderMappingSection,
  ColumnMappingSection,
  AnomalyConfigSection,
} from "../user-config";

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function UserConfigPage({ bridge }: { bridge: BridgeProp }) {
  return (
    <div>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-slate-800">用户配置</h2>
        <p className="text-xs text-slate-500 mt-0.5">管理与业务处理无关的个人偏好设置</p>
      </div>

      <div className="space-y-2">
        <LLMConfigSection bridge={bridge} />
        <MineBaseSection bridge={bridge} />
        <FileKeywordsSection bridge={bridge} />
        <HeaderMappingSection bridge={bridge} />
        <ColumnMappingSection bridge={bridge} />
        <AnomalyConfigSection bridge={bridge} />
      </div>
    </div>
  );
}
