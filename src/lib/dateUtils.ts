/** 日期选择与业务日期计算统一使用浏览器/桌面的本地时区。 */

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** 将本地 Date 格式化为业务日期字符串 YYYY-MM-DD。 */
export function formatLocalDate(value: Date | undefined): string {
  if (!value) return "";
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

/** 将 YYYY-MM-DD 解析为本地零点 Date，不经过 UTC。 */
export function parseLocalDate(value: string): Date | undefined {
  if (!value) return undefined;
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return undefined;
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

/** 返回当前本地日历日期的零点。 */
export function localToday(): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

/** 按本地日历日期增减天数，避免通过 UTC ISO 字符串发生日期偏移。 */
export function addLocalDays(value: Date, days: number): Date {
  const result = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  result.setDate(result.getDate() + days);
  return result;
}

export function localTodayString(): string {
  return formatLocalDate(localToday());
}

export function localYesterdayString(): string {
  return formatLocalDate(addLocalDays(localToday(), -1));
}

/** 返回带本地 UTC 偏移的 ISO 时间，供前端无后端时间时使用。 */
export function localDateTimeISO(value: Date = new Date()): string {
  const offsetMinutes = -value.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteOffset = Math.abs(offsetMinutes);
  const offsetHours = Math.floor(absoluteOffset / 60);
  const offsetRemainder = absoluteOffset % 60;
  return [
    `${formatLocalDate(value)}T${pad(value.getHours())}:${pad(value.getMinutes())}:${pad(value.getSeconds())}.${String(value.getMilliseconds()).padStart(3, "0")}`,
    `${sign}${pad(offsetHours)}:${pad(offsetRemainder)}`,
  ].join("");
}

