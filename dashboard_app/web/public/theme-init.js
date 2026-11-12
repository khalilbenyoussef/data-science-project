// Appliqué avant le premier rendu pour éviter tout clignotement de thème ou de sens.
(function () {
  try {
    var lang = window.localStorage.getItem("finova.locale") || "fr";
    var theme = window.localStorage.getItem("finova.theme");
    if (theme !== "light" && theme !== "dark") {
      theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    }
    var root = document.documentElement;
    root.lang = lang;
    root.dir = lang === "ar" ? "rtl" : "ltr";
    root.setAttribute("data-theme", theme);
    root.style.colorScheme = theme;
  } catch (error) {
    /* stockage indisponible */
  }
})();
