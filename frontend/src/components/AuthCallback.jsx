import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const navigate = useNavigate();
  const { googleSession } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const hash = window.location.hash;
    const match = hash.match(/session_id=([^&]+)/);
    const sessionId = match ? match[1] : null;
    (async () => {
      if (sessionId) {
        try {
          await googleSession(sessionId);
        } catch (e) {
          console.error("Google auth failed", e);
        }
      }
      window.history.replaceState(null, "", window.location.pathname);
      navigate("/dashboard", { replace: true });
    })();
  }, [googleSession, navigate]);

  return (
    <div className="stitch-wallpaper min-h-screen flex items-center justify-center">
      <div className="stitch-spinner" />
    </div>
  );
}
