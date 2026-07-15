import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

const FeaturesContext = createContext(null);
export const useFeatures = () => useContext(FeaturesContext);

const DEFAULTS = { chat: true, projects: true, assets: true, integrations: true, ai_assistant: true, friends: true };

export function FeaturesProvider({ children }) {
  const [flags, setFlags] = useState(DEFAULTS);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/features");
      setFlags({ ...DEFAULTS, ...data });
    } catch (e) {}
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return <FeaturesContext.Provider value={{ flags, refresh }}>{children}</FeaturesContext.Provider>;
}
