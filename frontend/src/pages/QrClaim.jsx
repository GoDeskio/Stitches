import { useEffect, useState, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function QrClaim() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [status, setStatus] = useState("loading");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const token = params.get("token");
    if (!token) { setStatus("error"); return; }
    (async () => {
      try {
        const { data } = await api.post("/auth/qr/claim", { token });
        if (data?.token) localStorage.setItem("stitches_token", data.token);
        setUser(data.user);
        setStatus("success");
        setTimeout(() => navigate("/dashboard", { replace: true }), 900);
      } catch (e) {
        setStatus("error");
      }
    })();
  }, [params, navigate, setUser]);

  return (
    <div className="stitch-wallpaper min-h-screen flex items-center justify-center p-6">
      <div className="neu-raised rounded-[1.75rem] p-10 max-w-sm w-full text-center animate-fade-up" data-testid="qr-claim-card">
        <div className="flex justify-center mb-6">
          <img src="/logo.png" alt="Stitches" className="w-14 h-14 object-contain" />
        </div>
        {status === "loading" && (
          <div data-testid="qr-claim-loading">
            <Loader2 className="w-10 h-10 text-primary-stitch animate-spin mx-auto mb-4" />
            <h1 className="font-head font-bold text-2xl mb-1" style={{ color: "var(--text)" }}>Signing you in…</h1>
            <p className="text-sm text-muted-stitch">Linking this device to your Stitches account.</p>
          </div>
        )}
        {status === "success" && (
          <div data-testid="qr-claim-success">
            <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <h1 className="font-head font-bold text-2xl mb-1" style={{ color: "var(--text)" }}>You're in!</h1>
            <p className="text-sm text-muted-stitch">Taking you to your dashboard…</p>
          </div>
        )}
        {status === "error" && (
          <div data-testid="qr-claim-error">
            <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h1 className="font-head font-bold text-2xl mb-1" style={{ color: "var(--text)" }}>Code expired</h1>
            <p className="text-sm text-muted-stitch mb-6">This login code is invalid, expired or already used. Generate a fresh one on your dashboard.</p>
            <button data-testid="qr-claim-login-btn" onClick={() => navigate("/login")} className="neu-primary rounded-2xl px-6 py-3 font-semibold w-full">
              Go to login
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
