import { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext(null);
export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => localStorage.getItem("stitches_theme") || "dark");
  const [scale, setScaleState] = useState(() => {
    // v2: default interface size is 70% (site-wide 30% reduction), migrating older visitors once
    if (localStorage.getItem("stitches_scale_v") !== "2") return 0.7;
    const v = localStorage.getItem("stitches_scale");
    return v ? parseFloat(v) : 0.7;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    localStorage.setItem("stitches_theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.style.setProperty("--ui-scale", scale);
    localStorage.setItem("stitches_scale", String(scale));
    localStorage.setItem("stitches_scale_v", "2");
  }, [scale]);

  const setTheme = (t) => setThemeState(t);
  const toggleTheme = () => setThemeState((t) => (t === "dark" ? "light" : "dark"));
  const setScale = (s) => setScaleState(s);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme, scale, setScale }}>
      {children}
    </ThemeContext.Provider>
  );
}
