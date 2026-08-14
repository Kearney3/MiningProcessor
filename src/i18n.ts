import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import zh from "./locales/zh.json";
import en from "./locales/en.json";
import mn from "./locales/mn.json";

export const DEFAULT_LANGUAGE = "zh" as const;
export const SUPPORTED_LANGUAGES = ["zh", "en", "mn"] as const;
export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number];
export const LANGUAGE_STORAGE_KEY = "lang";

export const I18N_NAMESPACES = [
  "common",
  "app",
  "pages",
  "components",
  "userConfig",
  "lib",
  "hooks",
] as const;
export type I18nNamespace = (typeof I18N_NAMESPACES)[number];

export const LANGUAGE_OPTIONS: ReadonlyArray<{
  code: LanguageCode;
  label: string;
}> = [
  { code: "zh", label: "中文" },
  { code: "en", label: "EN" },
  { code: "mn", label: "МН" },
];

export function normalizeLanguage(value: string | null | undefined): LanguageCode | null {
  if (!value) return null;
  const base = value.trim().toLowerCase().replace(/_/g, "-").split("-")[0];
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(base)
    ? (base as LanguageCode)
    : null;
}

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage may be unavailable in private mode or during SSR/test setup.
  }
}

function getInitialLanguage(): LanguageCode {
  const saved = normalizeLanguage(readStorage(LANGUAGE_STORAGE_KEY));
  if (saved) return saved;

  const browserLanguage = typeof navigator !== "undefined" ? normalizeLanguage(navigator.language) : null;
  return browserLanguage ?? DEFAULT_LANGUAGE;
}

const resources = {
  zh: { ...zh },
  en: { ...en },
  mn: { ...mn },
};

i18n.use(initReactI18next).init({
  resources,
  lng: getInitialLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: SUPPORTED_LANGUAGES,
  defaultNS: "common",
  ns: I18N_NAMESPACES,
  keySeparator: false,
  nsSeparator: ":",
  load: "languageOnly",
  cleanCode: true,
  nonExplicitSupportedLngs: true,
  returnEmptyString: false,
  interpolation: {
    escapeValue: false,
    prefix: "{",
    suffix: "}",
  },
  react: {
    useSuspense: false,
  },
});

i18n.on("languageChanged", (language) => {
  const normalized = normalizeLanguage(language) ?? DEFAULT_LANGUAGE;
  writeStorage(LANGUAGE_STORAGE_KEY, normalized);
  if (typeof document !== "undefined") {
    document.documentElement.lang = normalized;
    document.documentElement.dir = "ltr";
  }
});

const activeLanguage = normalizeLanguage(i18n.resolvedLanguage ?? i18n.language) ?? DEFAULT_LANGUAGE;
writeStorage(LANGUAGE_STORAGE_KEY, activeLanguage);
if (typeof document !== "undefined") {
  document.documentElement.lang = activeLanguage;
  document.documentElement.dir = "ltr";
}

export default i18n;
