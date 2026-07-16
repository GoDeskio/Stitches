import { useEffect, useState, useCallback } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Smartphone, RefreshCw } from "lucide-react";
import api from "@/lib/api";

export default function QrLoginCard() {
  const [token, setToken] = useState(null);
  const [left, setLeft] = useState(0);
  const [loading, setLoading] = useState(true);

  const gen = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/qr/generate");
      setToken(data.token);
      setLeft(data.expires_in_seconds);
    } catch (e) {
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { gen(); }, [gen]);

  useEffect(() => {
    if (left <= 0) return;
    const t = setTimeout(() => setLeft((p) => p - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);

  useEffect(() => {
    if (token && left === 0) gen();
  }, [left, token, gen]);

  const url = token ? `${window.location.origin}/qr-login/claim?token=${token}` : "";

  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up flex flex-col sm:flex-row items-center gap-7" data-testid="qr-login-card">
      <div className="neu-pressed rounded-2xl p-4 bg-white shrink-0" style={{ background: "#fff" }}>
        {loading || !token ? (
          <div className="w-[168px] h-[168px] flex items-center justify-center">
            <RefreshCw className="w-8 h-8 text-neutral-400 animate-spin" />
          </div>
        ) : (
          <QRCodeSVG data-testid="qr-login-code" value={url} size={168} level="M" includeMargin={false} />
        )}
      </div>
      <div className="flex-1 text-center sm:text-left">
        <div className="flex items-center gap-2 justify-center sm:justify-start mb-2">
          <div className="neu-sm w-10 h-10 rounded-2xl flex items-center justify-center">
            <Smartphone className="w-5 h-5 text-primary-stitch" />
          </div>
          <h2 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Log in on your phone</h2>
        </div>
        <p className="text-sm text-muted-stitch mb-4">
          Open the Stitches app (or camera) on your phone and scan this code to sign in instantly — no password needed. Your devices stay in sync.
        </p>
        <div className="flex items-center gap-3 justify-center sm:justify-start">
          <span className="neu-sm text-xs px-3 py-1.5 rounded-full text-muted-stitch font-semibold" data-testid="qr-login-timer">
            {token ? `Refreshes in ${left}s` : "Preparing…"}
          </span>
          <button data-testid="qr-login-refresh" onClick={gen} className="neu-btn rounded-full px-4 py-1.5 text-sm font-semibold flex items-center gap-2 text-primary-stitch">
            <RefreshCw className="w-4 h-4" /> New code
          </button>
        </div>
      </div>
    </div>
  );
}
