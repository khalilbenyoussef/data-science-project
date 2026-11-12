// Sélecteurs globaux : langue (FR / EN / AR) et thème (clair / sombre).
import { LANGUAGES, usePreferences } from "./preferences";
import { t } from "./i18n";

const ICON_SUN =
  "M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M18.4 5.6l1.4-1.4M4.2 19.8l1.4-1.4M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z";
const ICON_MOON = "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z";

export function DisplayControls({ floating = false }: { floating?: boolean }) {
  const { lang, setLang, theme, toggleTheme } = usePreferences();
  const themeAction = theme === "dark" ? t("Passer en mode clair") : t("Passer en mode sombre");
  return (
    <div className={`display-controls${floating ? " floating" : ""}`}>
      <div className="lang-switch" role="group" aria-label={t("Choisir la langue")}>
        {LANGUAGES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={lang === item.id ? "active" : ""}
            onClick={() => setLang(item.id)}
            aria-pressed={lang === item.id}
            title={item.label}
            lang={item.id}
          >
            {item.short}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="theme-switch"
        onClick={toggleTheme}
        title={themeAction}
        aria-label={themeAction}
      >
        <svg
          viewBox="0 0 24 24"
          width="17"
          height="17"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d={theme === "dark" ? ICON_SUN : ICON_MOON} />
        </svg>
        <span>{theme === "dark" ? t("Clair") : t("Sombre")}</span>
      </button>
    </div>
  );
}
