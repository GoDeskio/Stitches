import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";
import { CreditCard, ShieldCheck, RotateCcw } from "lucide-react";

const fmtMoney = (n) => "$" + (Number(n) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const formatCard = (v) => v.replace(/\D/g, "").slice(0, 19).replace(/(.{4})/g, "$1 ").trim();
const formatExp = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 4);
  return d.length >= 3 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
};

export function PaymentsTab() {
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState(null);
  const [txs, setTxs] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [f, setF] = useState({ amount: "10.00", email: "", description: "", ccnumber: "", ccexp: "", cvv: "" });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const loadStats = () => api.get("/admin/payments/stats").then(({ data }) => setStats(data)).catch(() => {});
  const loadTxs = () => api.get("/admin/payments/transactions").then(({ data }) => setTxs(data.transactions)).catch(() => setTxs([]));

  useEffect(() => {
    api.get("/admin/payments/config").then(({ data }) => setConfig(data)).catch(() => setConfig({ configured: false }));
    loadStats();
    loadTxs();
  }, []);

  const charge = async () => {
    if (!(parseFloat(f.amount) > 0)) { toast.error("Enter a valid amount"); return; }
    if (f.ccnumber.replace(/\s/g, "").length < 12 || f.ccexp.replace(/\D/g, "").length < 4) {
      toast.error("Enter a valid card number and expiry"); return;
    }
    setProcessing(true);
    try {
      const { data } = await api.post("/admin/payments/charge", {
        amount: f.amount, email: f.email, description: f.description,
        ccnumber: f.ccnumber, ccexp: f.ccexp, cvv: f.cvv,
      });
      if (data.success) {
        toast.success(`Charged ${fmtMoney(f.amount)} · ${data.transaction.nmi_transaction_id}`);
        setF((p) => ({ ...p, ccnumber: "", ccexp: "", cvv: "" }));
        loadStats(); loadTxs();
      } else {
        toast.error(data.error || "Payment declined");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Payment failed");
    } finally {
      setProcessing(false);
    }
  };

  const refund = async (tx) => {
    if (!window.confirm(`Refund ${fmtMoney(tx.amount)} for ${tx.email || tx.tx_id}?`)) return;
    try {
      const { data } = await api.post(`/admin/payments/refund/${tx.tx_id}`);
      toast.success(`${data.op === "void" ? "Voided" : "Refunded"} ${fmtMoney(tx.amount)}`);
      loadStats(); loadTxs();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Refund failed");
    }
  };

  if (!config) return <Loader />;

  const statCards = stats ? [
    { label: "Collected", val: fmtMoney(stats.collected), sub: `${stats.sales} sale(s)` },
    { label: "Successful sales", val: stats.sales, sub: "" },
    { label: "Failed", val: stats.failed, sub: "declined" },
    { label: "Refunds / voids", val: stats.refunds, sub: "" },
  ] : [];

  const statusColor = { success: "#16a34a", failed: "#ef4444", refunded: "#f59e0b" };

  return (
    <div className="space-y-6" data-testid="payments-tab">
      {!config.configured && (
        <div className="neu-raised rounded-[1.5rem] p-5 text-sm" style={{ color: "var(--text)" }} data-testid="payments-not-configured">
          Payment gateway is not configured. Add your NMI keys to enable charging.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s, i) => (
          <div key={i} data-testid={`payments-stat-${s.label.toLowerCase().replace(/[^a-z]/g, "-")}`} className="neu-raised rounded-[1.5rem] p-5 animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
            <p className="text-xs text-muted-stitch">{s.label}</p>
            <p className="text-3xl font-head font-bold mt-1" style={{ color: "var(--text)" }}>{s.val}</p>
            {s.sub && <p className="text-xs text-muted-stitch mt-1">{s.sub}</p>}
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Charge form */}
        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up lg:col-span-2" data-testid="payments-charge-card">
          <div className="flex items-center gap-3 mb-1">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><CreditCard className="w-5 h-5 text-primary-stitch" /></div>
            <div>
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Take a payment</h3>
              <p className="text-sm text-muted-stitch">Charge a card via NMI.{config.sandbox ? " Test mode." : ""}</p>
            </div>
          </div>

          {config.sandbox && (
            <p className="text-xs text-muted-stitch mt-3">Test card: <span className="font-mono-stitch">4111 1111 1111 1111</span> · expiry <span className="font-mono-stitch">10/29</span> · CVV <span className="font-mono-stitch">123</span></p>
          )}

          <div className="space-y-3 mt-4">
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-semibold text-muted-stitch">Amount ({config.currency || "USD"})</label>
                <input data-testid="payments-amount" type="number" step="0.01" min="0" value={f.amount} onChange={(e) => set("amount", e.target.value)} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
              </div>
              <div className="flex-1">
                <label className="text-xs font-semibold text-muted-stitch">Customer email</label>
                <input data-testid="payments-email" value={f.email} onChange={(e) => set("email", e.target.value)} placeholder="optional" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Description</label>
              <input data-testid="payments-description" value={f.description} onChange={(e) => set("description", e.target.value)} placeholder="optional" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Card number</label>
              <input data-testid="payments-ccnumber" inputMode="numeric" autoComplete="cc-number" value={f.ccnumber}
                onChange={(e) => set("ccnumber", formatCard(e.target.value))} placeholder="0000 0000 0000 0000"
                className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 font-mono-stitch" />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-semibold text-muted-stitch">Expiry (MM/YY)</label>
                <input data-testid="payments-ccexp" inputMode="numeric" autoComplete="cc-exp" value={f.ccexp}
                  onChange={(e) => set("ccexp", formatExp(e.target.value))} placeholder="MM/YY"
                  className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 font-mono-stitch" />
              </div>
              <div className="flex-1">
                <label className="text-xs font-semibold text-muted-stitch">CVV</label>
                <input data-testid="payments-cvv" inputMode="numeric" autoComplete="cc-csc" value={f.cvv}
                  onChange={(e) => set("cvv", e.target.value.replace(/\D/g, "").slice(0, 4))} placeholder="CVV"
                  className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 font-mono-stitch" />
              </div>
            </div>
            <button data-testid="payments-charge-btn" onClick={charge} disabled={!config.configured || processing}
              className="neu-primary rounded-2xl px-6 py-3.5 font-semibold w-full disabled:opacity-50">
              {processing ? "Processing…" : `Charge ${fmtMoney(f.amount)}`}
            </button>
            <p className="text-[11px] text-muted-stitch flex items-center gap-1.5 justify-center text-center"><ShieldCheck className="w-3.5 h-3.5 shrink-0" /> Sent securely over HTTPS to NMI. For a public checkout, upgrade to Collect.js tokenization for full PCI-SAQ&nbsp;A.</p>
          </div>
        </div>

        {/* Transactions */}
        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up lg:col-span-3" data-testid="payments-transactions">
          <h3 className="font-head font-bold text-xl mb-4" style={{ color: "var(--text)" }}>Recent transactions</h3>
          {!txs ? <Loader /> : txs.length === 0 ? (
            <p className="text-sm text-muted-stitch py-8 text-center">No transactions yet. Take a payment to see it here.</p>
          ) : (
            <div className="space-y-2">
              {txs.map((t) => (
                <div key={t.tx_id} data-testid="payments-tx-row" className="neu-pressed rounded-2xl px-4 py-3 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full neu-sm flex items-center justify-center shrink-0"><CreditCard className="w-4 h-4 text-primary-stitch" /></div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>
                      {fmtMoney(t.amount)} <span className="text-muted-stitch font-normal">· {t.type}</span>
                      {t.card_last4 ? <span className="text-muted-stitch font-normal"> · ****{t.card_last4}</span> : null}
                    </p>
                    <p className="text-xs text-muted-stitch truncate">
                      {t.email || t.description || t.nmi_transaction_id}{t.response_text ? ` · ${t.response_text}` : ""}
                    </p>
                  </div>
                  <span className="text-[11px] text-muted-stitch shrink-0 hidden sm:block">{new Date(t.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                  <span className="text-[11px] font-bold uppercase px-2 py-1 rounded-full shrink-0" style={{ color: "#fff", background: statusColor[t.status] || "#6b7280" }}>{t.status}</span>
                  {t.type === "sale" && t.status === "success" && !t.refunded && (
                    <button data-testid="payments-refund-btn" onClick={() => refund(t)} title="Refund / void" className="neu-btn rounded-xl px-2.5 py-2 text-red-500 shrink-0"><RotateCcw className="w-4 h-4" /></button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
