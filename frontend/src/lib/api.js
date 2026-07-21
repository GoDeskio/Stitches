import axios from "axios";

// Falls back to the current origin when REACT_APP_BACKEND_URL is unset, so prebuilt
// (domain-agnostic) Docker images work behind any domain/reverse proxy. Same-origin
// requests are proxied to the backend by nginx (see deploy/self-host/nginx.docker.conf).
const BACKEND = process.env.REACT_APP_BACKEND_URL || (typeof window !== "undefined" ? window.location.origin : "");
export const BACKEND_ORIGIN = BACKEND;
export const API = `${BACKEND}/api`;

const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("stitches_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
