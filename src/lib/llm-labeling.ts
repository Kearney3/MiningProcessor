import i18n from "../i18n";

const COLUMN_HINTS: Record<string, string[]> = {
  content_column: ["维修内容", "维修描述", "故障描述", "内容", "维修记录"],
  category_column: ["大类", "分类", "故障大类", "系统分类"],
  minor_column: ["小类", "子分类", "故障小类", "详细分类"],
  status_column: ["分类方式", "标注方式", "分类状态", "标注状态", "分类来源"],
};

const OUTPUT_COLUMN_DEFAULTS: Record<string, string> = {
  category_column: "大类",
  minor_column: "小类",
  status_column: "分类方式",
};

export function autoDetectColumn(columns: string[], field: string): string {
  const hints = COLUMN_HINTS[field] || [];
  for (const hint of hints) {
    if (columns.includes(hint)) return hint;
  }
  if (field === "content_column") return columns[0] || "";
  return OUTPUT_COLUMN_DEFAULTS[field] || "";
}

export function validateColumnMapping(
  contentColumn: string,
  categoryColumn: string,
  minorColumn: string,
  statusColumn: string,
): string | null {
  const entries = [
    [i18n.t("lib:llm-labeling.维修内容列_6809"), contentColumn],
    [i18n.t("lib:llm-labeling.大类列_b1b1"), categoryColumn],
    [i18n.t("lib:llm-labeling.小类列_aa19"), minorColumn],
    [i18n.t("lib:llm-labeling.分类方式列_4266"), statusColumn],
  ];
  const rolesByColumn = new Map<string, string[]>();
  for (const [role, column] of entries) {
    if (!column) return i18n.t("lib:llm-labeling.$不能为空_0c87", { role });
    rolesByColumn.set(column, [...(rolesByColumn.get(column) || []), role]);
  }
  const conflict = [...rolesByColumn.entries()].find(([, roles]) => roles.length > 1);
  return conflict
    ? i18n.t("lib:llm-labeling.columnConflict", { column: conflict[0], roles: conflict[1].join(", ") })
    : null;
}
