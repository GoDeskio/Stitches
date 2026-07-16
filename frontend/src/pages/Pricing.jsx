import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, X, ArrowLeft, ShieldCheck, Sparkles } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const fmtMoney = (n) => "$" + (Number(n) || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
const intervalLabel = { month: "/mo", year: "/yr", once: " once" };
const formatCard = (v) => v.replace(/\D/g, "").slice(0, 19).replace(/(.{4})/g, "$1 ").trim();
const formatExp = (v) => { const d = v.replace(/\D/g, "").slice(0, 4); return d.length >= 3 ? `${d.slice(0, 2)}/${d.slice(2)}` : d; };

export default function Pricing() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [plans, setPlans] = useState(null);
  const [checkout, setCheckout] = useState(null);
  const [billing, setBilling] = useState("month");

  useEffect(() => {
    api.get("/plans").then(({ data }) => setPlans(data.plans)).catch(() => setPlans([]));
  }, []);

  const hasYearly = (plans || []).some((p) => Number(p.yearly_price) > 0 && Number(p.price) > 0);
  const priceFor = (p) => (billing === "year" && Number(p.yearly_price) > 0 ? Number(p.yearly_price) : Number(p.price) || 0);
  const intervalFor = (p) => (billing === "year" && Number(p.yearly_price) > 0 ? "year" : p.interval);
  const savePct = (p) => {
    const m = Number(p.price) || 0, y = Number(p.yearly_price) || 0;
    if (billing !== "year" || m <= 0 || y <= 0) return 0;
    return Math.max(0, Math.round((1 - y / (m * 12)) * 100));
  };

  const pick = (p) => {
    if (priceFor(p) <= 0) {
      if (user && user !== false) navigate("/dashboard"); else navigate("/login");
      return;
    }
    setCheckout({ plan: p, billing: intervalFor(p), amount: priceFor(p) });
  };

  return (
    <div className="min-h-screen w-full" style={{ background: "var(--bg)" }}>
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-10">
          <button data-testid="pricing-back" onClick={() => navigate("/")} className="neu-btn rounded-full px-4 py-2.5 text-sm font-semibold text-primary-stitch flex items-center gap-2"><ArrowLeft className="w-4 h-4" /> Back</button>
          <button data-testid="pricing-login" onClick={() => navigate(user && user !== false ? "/dashboard" : "/login")} className="neu-btn rounded-full px-4 py-2.5 text-sm font-semibold">{user && user !== false ? "Dashboard" : "Login"}</button>
        </div>

        <div className="text-center mb-12 animate-fade-up">
          <h1 className="font-head font-black text-4xl sm:text-5xl lg:text-6xl" style={{ color: "var(--text)" }}>Simple, honest pricing</h1>
          <p className="text-base text-muted-stitch mt-4 max-w-xl mx-auto">Pick the plan that fits your team. Upgrade, downgrade or cancel anytime.</p>
          {hasYearly && (
            <div className="inline-flex items-center gap-1 mt-7 neu-pressed rounded-full p-1" data-testid="billing-toggle">
              <button data-testid="billing-monthly" onClick={() => setBilling("month")}
                className={`px-5 py-2 rounded-full text-sm font-semibold transition-all ${billing === "month" ? "neu-primary" : "text-muted-stitch"}`}>Monthly</button>
              <button data-testid="billing-yearly" onClick={() => setBilling("year")}
                className={`px-5 py-2 rounded-full text-sm font-semibold transition-all flex items-center gap-2 ${billing === "year" ? "neu-primary" : "text-muted-stitch"}`}>
                Yearly <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: billing === "year" ? "rgba(255,255,255,0.25)" : "var(--primary)", color: "#fff" }}>Save more</span>
              </button>
            </div>
          )}
        </div>

        {!plans ? (
          <div className="flex justify-center py-20"><div className="stitch-spinner" /></div>
        ) : plans.length === 0 ? (
          <p className="text-center text-muted-stitch py-20" data-testid="pricing-empty">Plans are being set up. Please check back soon.</p>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 items-start" data-testid="pricing-grid">
            {plans.map((p, i) => (
              <div key={p.plan_id} data-testid="pricing-card"
                className={`rounded-[1.75rem] p-7 animate-fade-up relative ${p.highlighted ? "neu-raised ring-2" : "neu-raised"}`}
                style={{ animationDelay: `${i * 70}ms`, ...(p.highlighted ? { boxShadow: "0 0 0 2px var(--primary), 10px 10px 30px rgba(0,0,0,0.5)" } : {}) }}>
                {p.highlighted && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-[11px] font-bold uppercase tracking-wide px-3 py-1 rounded-full text-white flex items-center gap-1" style={{ background: "var(--primary)" }}><Sparkles className="w-3 h-3" /> Most popular</span>
                )}
                <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{p.name}</h3>
                {p.description && <p className="text-sm text-muted-stitch mt-1 min-h-[2.5rem]">{p.description}</p>}
                <p className="font-head font-black text-5xl mt-4" style={{ color: "var(--text)" }}>
                  {fmtMoney(priceFor(p))}<span className="text-base font-normal text-muted-stitch">{priceFor(p) > 0 ? (intervalLabel[intervalFor(p)] || "") : ""}</span>
                </p>
                {savePct(p) > 0 && <p className="text-xs font-semibold text-primary-stitch mt-1" data-testid="pricing-save">Save {savePct(p)}% vs monthly</p>}
                <button data-testid="pricing-select" onClick={() => pick(p)}
                  className={`w-full mt-6 rounded-2xl py-3.5 font-semibold text-sm transition-transform hover:-translate-y-0.5 ${p.highlighted ? "neu-primary" : "neu-btn text-primary-stitch"}`}>
                  {p.cta || "Get started"}
                </button>
                <ul className="mt-6 space-y-2.5">
                  {(p.features || []).map((fe, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm" style={{ color: "var(--text)" }}>
                      <Check className="w-4 h-4 text-primary-stitch mt-0.5 shrink-0" /> {fe}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>

      {checkout && <CheckoutModal plan={checkout.plan} billing={checkout.billing} amount={checkout.amount} onClose={() => setCheckout(null)} />}
    </div>
  );
}

function CheckoutModal({ plan, billing, amount, onClose }) {
  const [f, setF] = useState({ name: "", email: "", ccnumber: "", ccexp: "", cvv: "" });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const pay = async () => {
    setErr("");
    if (!f.email.includes("@")) { setErr("Enter a valid email"); return; }
    if (f.ccnumber.replace(/\s/g, "").length < 12 || f.ccexp.replace(/\D/g, "").length < 4) { setErr("Enter valid card details"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/checkout/plan", {
        plan_id: plan.plan_id, billing, name: f.name, email: f.email,
        ccnumber: f.ccnumber, ccexp: f.ccexp, cvv: f.cvv,
      });
      if (data.success) setDone(true);
      else setErr(data.error || "Payment declined");
    } catch (e) {
      setErr(e?.response?.data?.detail || "Payment failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={onClose} data-testid="checkout-modal">
      <div className="neu-raised rounded-[1.75rem] p-7 max-w-md w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose} data-testid="checkout-close" className="float-right neu-btn rounded-full p-1.5 text-muted-stitch"><X className="w-4 h-4" /></button>
        {done ? (
          <div className="text-center py-6" data-testid="checkout-success">
            <div className="w-14 h-14 rounded-full mx-auto flex items-center justify-center mb-4 neu-primary"><Check className="w-7 h-7 text-white" /></div>
            <h2 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>You're all set!</h2>
            <p className="text-sm text-muted-stitch mt-2">Your {plan.name} plan is active. A receipt is on its way.</p>
            <button onClick={onClose} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-5">Done</button>
          </div>
        ) : (
          <>
            <h2 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Checkout — {plan.name}</h2>
            <p className="text-sm text-muted-stitch mt-1">{fmtMoney(amount)}{intervalLabel[billing] || ""}</p>
            <div className="space-y-3 mt-5">
              <input data-testid="checkout-name" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="Full name" className="neu-input w-full rounded-2xl py-3 px-4 text-sm" />
              <input data-testid="checkout-email" value={f.email} onChange={(e) => set("email", e.target.value)} placeholder="Email *" className="neu-input w-full rounded-2xl py-3 px-4 text-sm" />
              <input data-testid="checkout-ccnumber" inputMode="numeric" value={f.ccnumber} onChange={(e) => set("ccnumber", formatCard(e.target.value))} placeholder="Card number" className="neu-input w-full rounded-2xl py-3 px-4 text-sm font-mono-stitch" />
              <div className="flex gap-3">
                <input data-testid="checkout-ccexp" inputMode="numeric" value={f.ccexp} onChange={(e) => set("ccexp", formatExp(e.target.value))} placeholder="MM/YY" className="neu-input flex-1 rounded-2xl py-3 px-4 text-sm font-mono-stitch" />
                <input data-testid="checkout-cvv" inputMode="numeric" value={f.cvv} onChange={(e) => set("cvv", e.target.value.replace(/\D/g, "").slice(0, 4))} placeholder="CVV" className="neu-input flex-1 rounded-2xl py-3 px-4 text-sm font-mono-stitch" />
              </div>
              {err && <p className="text-sm text-red-500" data-testid="checkout-error">{err}</p>}
              <button data-testid="checkout-pay" onClick={pay} disabled={busy} className="neu-primary rounded-2xl py-3.5 font-semibold w-full disabled:opacity-50">{busy ? "Processing…" : `Pay ${fmtMoney(amount)}`}</button>
              <p className="text-[11px] text-muted-stitch flex items-center gap-1.5 justify-center"><ShieldCheck className="w-3.5 h-3.5" /> Secured by NMI. Encrypted in transit.</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
