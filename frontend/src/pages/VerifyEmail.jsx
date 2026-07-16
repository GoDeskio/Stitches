import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import api from "@/lib/api";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, ok: false, message: "" });

  useEffect(() => {
    const token = params.get("token");
    if (!token) { setState({ loading: false, ok: false, message: "No verification token provided." }); return; }
    api.get(`/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then(({ data }) => setState({ loading: false, ok: data.ok, message: data.message }))
      .catch(() => setState({ loading: false, ok: false, message: "Something went wrong verifying your email." }));
  }, [params]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: "var(--bg)" }}>
      <div data-testid="verify-email-card" className="neu-raised rounded-[1.75rem] p-10 max-w-md w-full text-center animate-fade-up">
        {state.loading ? (
          <>
            <Loader2 className="w-12 h-12 text-primary-stitch mx-auto animate-spin" />
            <h1 className="font-head font-bold text-2xl mt-5" style={{ color: "var(--text)" }}>Verifying…</h1>
          </>
        ) : state.ok ? (
          <>
            <CheckCircle2 className="w-14 h-14 mx-auto" style={{ color: "#16a34a" }} data-testid="verify-success-icon" />
            <h1 className="font-head font-bold text-2xl mt-5" style={{ color: "var(--text)" }}>Email verified</h1>
            <p className="text-sm text-muted-stitch mt-2">{state.message}</p>
          </>
        ) : (
          <>
            <XCircle className="w-14 h-14 mx-auto text-red-500" data-testid="verify-error-icon" />
            <h1 className="font-head font-bold text-2xl mt-5" style={{ color: "var(--text)" }}>Verification failed</h1>
            <p className="text-sm text-muted-stitch mt-2">{state.message}</p>
          </>
        )}
        {!state.loading && (
          <button data-testid="verify-continue-btn" onClick={() => navigate("/dashboard")}
            className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-6 w-full">Continue to Stitches</button>
        )}
      </div>
    </div>
  );
}
