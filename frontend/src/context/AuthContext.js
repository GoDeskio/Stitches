import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=unauth, obj=auth
  const [impersonating, setImpersonating] = useState(!!localStorage.getItem("stitches_admin_token"));

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (e) {
      setUser(false);
    }
  }, []);

  useEffect(() => {
    if (window.location.hash?.includes("session_id=")) return;
    checkAuth();
  }, [checkAuth]);

  const persist = (data) => {
    if (data?.token) localStorage.setItem("stitches_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    return persist(data);
  };

  const register = async (email, password, name) => {
    const { data } = await api.post("/auth/register", { email, password, name });
    return persist(data);
  };

  const googleSession = async (session_id) => {
    const { data } = await api.post("/auth/google/session", { session_id });
    return persist(data);
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) {}
    localStorage.removeItem("stitches_token");
    setUser(false);
  };

  const updateUser = (u) => setUser(u);

  const startImpersonation = (token, userObj) => {
    const current = localStorage.getItem("stitches_token");
    if (current) localStorage.setItem("stitches_admin_token", current);
    localStorage.setItem("stitches_token", token);
    setImpersonating(true);
    setUser(userObj);
  };

  const stopImpersonation = async () => {
    const adminTok = localStorage.getItem("stitches_admin_token");
    if (adminTok) localStorage.setItem("stitches_token", adminTok);
    localStorage.removeItem("stitches_admin_token");
    setImpersonating(false);
    await checkAuth();
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, googleSession, logout, updateUser, checkAuth, impersonating, startImpersonation, stopImpersonation }}>
      {children}
    </AuthContext.Provider>
  );
}
