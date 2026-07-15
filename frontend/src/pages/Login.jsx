import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Mail, Lock, User, ArrowRight, Eye, EyeOff } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/api";

export default function Login() {
  const navigate = useNavigate();
  const { user, login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user && user !== false) navigate("/dashboard", { replace: true });
  }, [user, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "login") {
        await login(form.email, form.password);
        toast.success("Welcome back to Stitches");
      } else {
        await register(form.email, form.password, form.name);
        toast.success("Account created — welcome!");
      }
      navigate("/dashboard", { replace: true });
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const googleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="stitch-wallpaper min-h-screen flex items-center justify-center p-6">
      <div className="relative z-10 w-full max-w-5xl grid lg:grid-cols-2 gap-8 items-center">
        {/* Brand side */}
        <div className="hidden lg:flex flex-col gap-8 p-10 animate-fade-up">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Stitches" className="w-16 h-16 object-contain" />
            <span className="font-head font-black text-3xl tracking-tight" style={{ color: "var(--text)" }}>Stitches</span>
          </div>
          <h1 className="font-head font-black text-5xl leading-[1.05] tracking-tight" style={{ color: "var(--text)" }}>
            Where Ideas are <span className="text-primary-stitch">Stitched</span> together.
          </h1>
          <p className="text-lg max-w-md text-muted-stitch">
            A tactile workspace for business & creative teams. Chat, collaborate on projects, share assets and plug in your favourite AI tools — all in one place.
          </p>
          <div className="flex gap-4">
            {["Real-time chat", "Shared assets", "AI + Integrations"].map((t) => (
              <div key={t} className="neu-sm rounded-full px-4 py-2 text-sm font-medium text-muted-stitch">{t}</div>
            ))}
          </div>
        </div>

        {/* Form side */}
        <div className="neu-raised rounded-[2rem] p-8 sm:p-10 animate-fade-up" data-testid="auth-card">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="neu-raised w-12 h-12 rounded-2xl flex items-center justify-center p-1.5">
              <img src="/logo.png" alt="Stitches" className="w-full h-full object-contain" />
            </div>
            <span className="font-head font-black text-2xl" style={{ color: "var(--text)" }}>Stitches</span>
          </div>

          <div className="neu-pressed rounded-full p-1.5 flex mb-8">
            {["login", "signup"].map((m) => (
              <button
                key={m}
                data-testid={`tab-${m}`}
                onClick={() => setMode(m)}
                className={`flex-1 rounded-full py-2.5 text-sm font-semibold transition-all ${mode === m ? "neu-primary" : "text-muted-stitch"}`}
              >
                {m === "login" ? "Sign In" : "Sign Up"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-5">
            {mode === "signup" && (
              <Field icon={User} placeholder="Full name" testid="name-input"
                value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
            )}
            <Field icon={Mail} type="email" placeholder="you@company.com" testid="email-input"
              value={form.email} onChange={(v) => setForm({ ...form, email: v })} />
            <Field icon={Lock} type="password" placeholder="Password" testid="password-input"
              value={form.password} onChange={(v) => setForm({ ...form, password: v })} />

            <button type="submit" disabled={loading} data-testid="submit-btn"
              className="neu-primary w-full rounded-2xl py-3.5 font-semibold flex items-center justify-center gap-2 disabled:opacity-70">
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : (
                <>{mode === "login" ? "Sign In" : "Create Account"} <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <div className="flex items-center gap-4 my-6">
            <div className="h-px flex-1" style={{ background: "var(--border)" }} />
            <span className="text-xs uppercase tracking-widest text-muted-stitch">or</span>
            <div className="h-px flex-1" style={{ background: "var(--border)" }} />
          </div>

          <button onClick={googleLogin} data-testid="google-login-btn"
            className="neu-btn w-full rounded-2xl py-3.5 font-semibold flex items-center justify-center gap-3" style={{ color: "var(--text)" }}>
            <GoogleIcon /> Continue with Google
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ icon: Icon, type = "text", placeholder, value, onChange, testid }) {
  const [show, setShow] = useState(false);
  const isPassword = type === "password";
  const effectiveType = isPassword ? (show ? "text" : "password") : type;
  return (
    <div className="relative">
      <Icon className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-muted-stitch" />
      <input
        data-testid={testid}
        type={effectiveType}
        required
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`neu-input w-full rounded-2xl py-3.5 pl-12 text-[0.95rem] ${isPassword ? "pr-12" : "pr-4"}`}
      />
      {isPassword && (
        <button type="button" data-testid="toggle-password" onClick={() => setShow((s) => !s)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-stitch hover:text-primary-stitch transition-colors">
          {show ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
        </button>
      )}
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38z" />
    </svg>
  );
}
