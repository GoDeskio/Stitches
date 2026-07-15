import { useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const STITCH_TEXTURE =
  "https://static.prod-images.emergentagent.com/jobs/a571e742-1f81-4c1f-b84c-9eec40db8ea8/images/c06bf8a339ae1402b4b3bd8a678af577a089c80af507fdb229466b01a46fee2d.png";

export default function Home() {
  const navigate = useNavigate();
  const { user } = useAuth();

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
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 p-1.5"
            style={{
              background: "rgba(20,15,17,0.55)",
              boxShadow: "6px 6px 14px rgba(0,0,0,0.55), -4px -4px 12px rgba(255,255,255,0.06)",
              backdropFilter: "blur(6px)",
            }}
          >
            <img src="/logo.png" alt="Stitches" className="w-full h-full object-contain" />
          </div>
          <span className="font-head font-semibold text-sm tracking-wide" style={{ color: "#F3E8EA" }}>
            Too Many Stitches
          </span>
        </div>

        {/* Top-right: small login button */}
        <button
          onClick={goLogin}
          data-testid="home-login-btn"
          className="absolute top-6 right-6 z-10 rounded-full px-5 py-2.5 flex items-center gap-2 text-sm font-semibold transition-transform hover:-translate-y-0.5"
          style={{
            background: "rgba(20,15,17,0.55)",
            color: "#F3E8EA",
            boxShadow: "6px 6px 14px rgba(0,0,0,0.55), -4px -4px 12px rgba(255,255,255,0.06)",
            backdropFilter: "blur(6px)",
          }}
        >
          <LogIn className="w-4 h-4" /> Login
        </button>

        {/* Center intentionally left blank for your logo */}
      </div>
    </div>
  );
}
