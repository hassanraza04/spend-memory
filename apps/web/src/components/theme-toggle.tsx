"use client";

import { useEffect, useState } from "react";

export type Theme = "personal-record" | "night-desk";

const storageKey = "spend-memory-theme";

function savedTheme(): Theme {
  try {
    return window.localStorage?.getItem(storageKey) === "night-desk" ? "night-desk" : "personal-record";
  } catch {
    return "personal-record";
  }
}

function saveTheme(theme: Theme) {
  try {
    window.localStorage?.setItem(storageKey, theme);
  } catch {
    // ponytail: keep the chosen theme for this session when browser storage is unavailable.
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => (typeof window === "undefined" ? "personal-record" : savedTheme()));

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
  }, [theme]);

  const nextTheme = theme === "personal-record" ? "night-desk" : "personal-record";

  return (
    <button className="theme-toggle" type="button" onClick={() => setTheme(nextTheme)}>
      <span aria-hidden="true">{theme === "personal-record" ? "◐" : "◑"}</span>
      <span>Use {nextTheme === "night-desk" ? "Night Desk" : "Personal Record"}</span>
    </button>
  );
}
