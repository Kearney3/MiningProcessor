import { useTranslation } from "react-i18next";
import { LANGUAGE_OPTIONS, normalizeLanguage } from "../i18n";

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation("common");
  const activeLanguage = normalizeLanguage(i18n.resolvedLanguage ?? i18n.language) ?? "zh";

  const handleChange = async (code: string) => {
    if (code === activeLanguage) return;
    await i18n.changeLanguage(code);
  };

  return (
    <div
      className="flex items-center gap-0.5 ml-2 rounded-md border border-slate-200 bg-slate-50 p-0.5"
      role="group"
      aria-label={t("common:changeLanguage")}
    >
      {LANGUAGE_OPTIONS.map((lang) => (
        <button
          key={lang.code}
          type="button"
          onClick={() => void handleChange(lang.code)}
          aria-pressed={activeLanguage === lang.code}
          title={t("common:switchToLanguage", { language: lang.label })}
          className={`px-2 py-0.5 text-[11px] font-medium rounded cursor-pointer transition-colors ${
            activeLanguage === lang.code
              ? "bg-white text-slate-800 shadow-sm"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          {lang.label}
        </button>
      ))}
    </div>
  );
}
