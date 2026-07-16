import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { LogIn, X, Sparkles, Tag } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";

const STITCH_TEXTURE =
  "https://static.prod-images.emergentagent.com/jobs/a571e742-1f81-4c1f-b84c-9eec40db8ea8/images/c06bf8a339ae1402b4b3bd8a678af577a089c80af507fdb229466b01a46fee2d.png";

export default function Home() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [note, setNote] = useState(null);
  const [showDemo, setShowDemo] = useState(false);
  const [demo, setDemo] = useState({ name: "", email: "", company: "", message: "" });
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const submitDemo = async () => {
    if (!demo.email.trim() || !demo.email.includes("@")) { setNote(null); return; }
    setSending(true);
    try {
      await api.post("/leads", { ...demo, source: "landing-demo" });
      setSent(true);
    } catch (e) {
      setSent(false);
    } finally { setSending(false); }
  };

  useEffect(() => {
    api.get("/site-config").then(({ data }) => {
      const ann = data.announcement || {};
      const ver = ann.updated_at || "default";
      if (ann.enabled && localStorage.getItem("stitches_welcome_dismissed") !== ver) {
        setNote({ ...ann, ver });
      }
    }).catch(() => {});
  }, []);

  const dismissNote = () => {
    if (note) localStorage.setItem("stitches_welcome_dismissed", note.ver);
    setNote(null);
  };

  const goLogin = () => {
    if (user && user !== false) navigate("/dashboard");
    else navigate("/login");
  };

  return (
    <div
      className="min-h-screen w-full relative flex items-center justify-center p-4"
      style={{ background: "var(--bg)" }}
    >
      {/* Stitched neumorphic canvas */}
      <div
        className="neu-raised rounded-[2rem] relative overflow-hidden animate-fade-up"
        style={{
          width: "calc(100vw - 2rem)",
          height: "calc(100vh - 2rem)",
          backgroundImage: `url('${STITCH_TEXTURE}')`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
        data-testid="home-canvas"
      >
        {/* subtle depth overlay */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ boxShadow: "inset 0 0 180px rgba(0,0,0,0.55)" }}
        />

        {/* Top-left: logo placeholder + brand */}
        <div className="absolute top-6 left-6 flex items-center gap-3 z-10" data-testid="home-brand">
          <img src="/logo.png" alt="Stitches" className="w-12 h-12 object-contain shrink-0" />
          <span className="font-head font-semibold text-sm tracking-wide" style={{ color: "#F3E8EA" }}>
            Too Many Stitches
          </span>
        </div>

        {/* Top-right: pricing + login buttons */}
        <div className="absolute top-6 right-6 z-10 flex items-center gap-2">
          <button
            onClick={() => navigate("/pricing")}
            data-testid="home-pricing-btn"
            className="rounded-full px-5 py-2.5 flex items-center gap-2 text-sm font-semibold transition-transform hover:-translate-y-0.5"
            style={{
              background: "rgba(20,15,17,0.55)",
              color: "#F3E8EA",
              boxShadow: "6px 6px 14px rgba(0,0,0,0.55), -4px -4px 12px rgba(255,255,255,0.06)",
              backdropFilter: "blur(6px)",
            }}
          >
            <Tag className="w-4 h-4" /> Pricing
          </button>
          <button
            onClick={goLogin}
            data-testid="home-login-btn"
            className="rounded-full px-5 py-2.5 flex items-center gap-2 text-sm font-semibold transition-transform hover:-translate-y-0.5"
            style={{
              background: "rgba(20,15,17,0.55)",
              color: "#F3E8EA",
              boxShadow: "6px 6px 14px rgba(0,0,0,0.55), -4px -4px 12px rgba(255,255,255,0.06)",
              backdropFilter: "blur(6px)",
            }}
          >
            <LogIn className="w-4 h-4" /> Login
          </button>
        </div>

        {/* Bottom-center: Request a demo CTA */}
        <button
          onClick={() => { setShowDemo(true); setSent(false); }}
          data-testid="request-demo-btn"
          className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10 rounded-full px-7 py-3 flex items-center gap-2 text-sm font-semibold transition-transform hover:-translate-y-0.5"
          style={{ background: "var(--primary)", color: "#fff", boxShadow: "6px 6px 16px rgba(0,0,0,0.5), -3px -3px 10px rgba(255,255,255,0.05)" }}
        >
          <Sparkles className="w-4 h-4" /> Request a demo
        </button>

        {/* Demo / lead-capture modal */}
        {showDemo && (
          <div className="absolute inset-0 z-30 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={() => setShowDemo(false)} data-testid="demo-modal">
            <div onClick={(e) => e.stopPropagation()} className="relative w-full max-w-md rounded-[1.75rem] p-8 animate-fade-up"
              style={{ background: "rgba(28,20,23,0.7)", backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)", border: "1px solid rgba(255,255,255,0.1)", boxShadow: "10px 10px 30px rgba(0,0,0,0.55)" }}>
              <button onClick={() => setShowDemo(false)} aria-label="Close" data-testid="demo-close" className="absolute top-4 right-4 rounded-full p-1.5" style={{ background: "rgba(255,255,255,0.08)", color: "#F3E8EA" }}><X className="w-4 h-4" /></button>
              {sent ? (
                <div className="text-center py-6">
                  <div className="w-14 h-14 rounded-full mx-auto flex items-center justify-center mb-4" style={{ background: "var(--primary)" }}><Sparkles className="w-7 h-7 text-white" /></div>
                  <h2 className="font-head font-bold text-xl" style={{ color: "#F9EEF0" }}>Thanks — we'll be in touch!</h2>
                  <p className="text-sm mt-2" style={{ color: "rgba(243,232,234,0.85)" }}>Your request has landed with our team.</p>
                </div>
              ) : (
                <>
                  <h2 className="font-head font-bold text-xl mb-1" style={{ color: "#F9EEF0" }}>Request a demo</h2>
                  <p className="text-sm mb-5" style={{ color: "rgba(243,232,234,0.8)" }}>Tell us a little about you and we'll reach out.</p>
                  <div className="space-y-3">
                    <input data-testid="demo-name" value={demo.name} onChange={(e) => setDemo({ ...demo, name: e.target.value })} placeholder="Your name" className="w-full rounded-2xl py-3 px-4 text-sm" style={{ background: "rgba(255,255,255,0.06)", color: "#F3E8EA", border: "1px solid rgba(255,255,255,0.12)" }} />
                    <input data-testid="demo-email" value={demo.email} onChange={(e) => setDemo({ ...demo, email: e.target.value })} placeholder="Work email *" className="w-full rounded-2xl py-3 px-4 text-sm" style={{ background: "rgba(255,255,255,0.06)", color: "#F3E8EA", border: "1px solid rgba(255,255,255,0.12)" }} />
                    <input data-testid="demo-company" value={demo.company} onChange={(e) => setDemo({ ...demo, company: e.target.value })} placeholder="Company" className="w-full rounded-2xl py-3 px-4 text-sm" style={{ background: "rgba(255,255,255,0.06)", color: "#F3E8EA", border: "1px solid rgba(255,255,255,0.12)" }} />
                    <textarea data-testid="demo-message" value={demo.message} onChange={(e) => setDemo({ ...demo, message: e.target.value })} rows={3} placeholder="What are you looking to do?" className="w-full rounded-2xl py-3 px-4 text-sm resize-none" style={{ background: "rgba(255,255,255,0.06)", color: "#F3E8EA", border: "1px solid rgba(255,255,255,0.12)" }} />
                  </div>
                  <button data-testid="demo-submit" onClick={submitDemo} disabled={sending} className="w-full mt-5 rounded-2xl py-3 font-semibold text-sm transition-transform hover:-translate-y-0.5" style={{ background: "var(--primary)", color: "#fff" }}>{sending ? "Sending…" : "Send request"}</button>
                </>
              )}
            </div>
          </div>
        )}

        {/* Center: dismissible glass welcome note */}
        {note && (
          <div className="absolute inset-0 z-20 flex items-center justify-center p-6 pointer-events-none">
            <div
              data-testid="welcome-note-card"
              className="pointer-events-auto relative w-full max-w-md rounded-[1.75rem] p-8 animate-fade-up"
              style={{
                background: "rgba(28,20,23,0.45)",
                boxShadow: "10px 10px 30px rgba(0,0,0,0.55), -6px -6px 20px rgba(255,255,255,0.06), inset 0 1px 0 rgba(255,255,255,0.08)",
                backdropFilter: "blur(18px)",
                WebkitBackdropFilter: "blur(18px)",
                border: "1px solid rgba(255,255,255,0.10)",
              }}
            >
              <button
                onClick={dismissNote}
                data-testid="welcome-note-close"
                aria-label="Close"
                className="absolute top-4 right-4 rounded-full p-1.5 transition-transform hover:-translate-y-0.5"
                style={{ background: "rgba(255,255,255,0.08)", color: "#F3E8EA" }}
              >
                <X className="w-4 h-4" />
              </button>
              <img src="/logo.png" alt="Stitches" className="w-12 h-12 object-contain mb-4" />
              {note.title && <h2 className="font-head font-bold text-xl mb-3" style={{ color: "#F9EEF0" }}>{note.title}</h2>}
              <p className="text-sm leading-relaxed whitespace-pre-line" style={{ color: "rgba(243,232,234,0.88)" }}>
                {note.message}
              </p>
              {note.signature && <p className="text-sm font-semibold mt-4 text-right" style={{ color: "#F3E8EA" }}>{note.signature}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
