// Préférences d'affichage : langue (français, anglais, arabe) et thème (clair, sombre).
// Persistées dans le navigateur et appliquées sur <html> (lang, dir, data-theme).
import { useEffect, useState } from "react";

export type Lang = "fr" | "en" | "ar";
export type Theme = "light" | "dark";

const LANG_KEY = "finova.locale";
const THEME_KEY = "finova.theme";
const EVENT = "finova:preferences";

export const LANGUAGES: { id: Lang; label: string; short: string }[] = [
  { id: "fr", label: "Français", short: "FR" },
  { id: "en", label: "English", short: "EN" },
  { id: "ar", label: "العربية", short: "AR" },
];

export function isLang(value: string | null): value is Lang {
  return value === "fr" || value === "en" || value === "ar";
}

export function getLang(): Lang {
  try {
    const stored = window.localStorage.getItem(LANG_KEY);
    if (isLang(stored)) return stored;
  } catch {
    /* stockage indisponible */
  }
  return "fr";
}

export function getTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
    if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) return "dark";
  } catch {
    /* stockage indisponible */
  }
  return "light";
}

const TITLES: Record<Lang, string> = {
  fr: "FinOVA — Tableau de bord de l'inclusion financière",
  en: "FinOVA — Financial inclusion dashboard",
  ar: "FinOVA — لوحة مؤشرات الإدماج المالي",
};

function apply(lang: Lang, theme: Theme) {
  const root = document.documentElement;
  root.lang = lang;
  root.dir = lang === "ar" ? "rtl" : "ltr";
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  document.title = TITLES[lang];
}

export function initPreferences() {
  apply(getLang(), getTheme());
}

function save(lang: Lang, theme: Theme) {
  try {
    window.localStorage.setItem(LANG_KEY, lang);
    window.localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* stockage indisponible : la préférence reste en mémoire */
  }
  apply(lang, theme);
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { lang, theme } }));
}

export function setLangPreference(lang: Lang) {
  save(lang, getTheme());
}

export function setThemePreference(theme: Theme) {
  save(getLang(), theme);
}

export function usePreferences(): {
  lang: Lang;
  theme: Theme;
  setLang: (lang: Lang) => void;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
} {
  const [lang, setLangState] = useState<Lang>(getLang);
  const [theme, setThemeState] = useState<Theme>(getTheme);

  useEffect(() => {
    const sync = () => {
      setLangState(getLang());
      setThemeState(getTheme());
    };
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return {
    lang,
    theme,
    setLang: (next: Lang) => {
      setLangPreference(next);
      setLangState(next);
    },
    setTheme: (next: Theme) => {
      setThemePreference(next);
      setThemeState(next);
    },
    toggleTheme: () => {
      const next: Theme = getTheme() === "dark" ? "light" : "dark";
      setThemePreference(next);
      setThemeState(next);
    },
  };
}
