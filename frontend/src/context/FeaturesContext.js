import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

const FeaturesContext = createContext(null);
export const useFeatures = () => useContext(FeaturesContext);

const DEFAULTS = { chat: true, projects: true, assets: true, integrations: true, ai_assistant: true, friends: true };

export function FeaturesProvider({ children }) {
  const [flags, setFlags] = useState(DEFAULTS);
  const [entitlements, setEntitlements] = useState({ features: DEFAULTS, gating: false, all_access: true, plan_name: null });

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/features");
      setFlags({ ...DEFAULTS, ...data });
    } catch (e) {}
    try {
      const { data } = await api.get("/me/entitlements");
      setEntitlements({ features: { ...DEFAULTS, ...(data.features || {}) }, gating: !!data.gating, all_access: !!data.all_access, plan_name: data.plan_name || null });
    } catch (e) {}
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const entitled = useCallback((flag) => {
    if (!flag) return true;
    if (!entitlements.gating || entitlements.all_access) return true;
    return entitlements.features?.[flag] !== false;
  }, [entitlements]);

  return <FeaturesContext.Provider value={{ flags, entitlements, entitled, refresh }}>{children}</FeaturesContext.Provider>;
}
