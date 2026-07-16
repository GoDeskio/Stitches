import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { NmiPayments } from "@nmipayments/nmi-pay-react";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";
import { CreditCard, ShieldCheck, RotateCcw } from "lucide-react";

const fmtMoney = (n) => "$" + (Number(n) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function PaymentsTab() {
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState(null);
  const [txs, setTxs] = useState(null);
  const [amount, setAmount] = useState("10.00");
  const [email, setEmail] = useState("");
  const [description, setDescription] = useState("");
  // Keep latest values available inside the onPay closure held by NmiPayments
  const form = useRef({ amount: "10.00", email: "", description: "" });
  useEffect(() => { form.current = { amount, email, description }; }, [amount, email, description]);

  const loadStats = () => api.get("/admin/payments/stats").then(({ data }) => setStats(data)).catch(() => {});
  const loadTxs = () => api.get("/admin/payments/transactions").then(({ data }) => setTxs(data.transactions)).catch(() => setTxs([]));

  useEffect(() => {
    api.get("/admin/payments/config").then(({ data }) => setConfig(data)).catch(() => setConfig({ configured: false }));
    loadStats();
    loadTxs();
  }, []);

  // Called by the Payment Component once the card form is completed and tokenized.
  // Return `true` on success or an error string to display in the widget.
  const handlePay = async (event) => {
    const { amount, email, description } = form.current;
    if (!(parseFloat(amount) > 0)) return "Enter a valid amount above.";
    try {
      const { data } = await api.post("/admin/payments/charge", {
        payment_token: event.token, amount, email, description,
      });
      if (data.success) {
        toast.success(`Charged ${fmtMoney(amount)} · ${data.transaction.nmi_transaction_id}`);
        loadStats(); loadTxs();
        return true;
      }
      toast.error(data.error || "Payment declined");
      return data.error || "Payment declined";
    } catch (e) {
      const msg = e?.response?.data?.detail || "Payment failed";
      toast.error(msg);
      return msg;
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
              <p className="text-sm text-muted-stitch">Charge a card securely via NMI.{config.sandbox ? " Test mode." : ""}</p>
            </div>
          </div>

          {config.sandbox && (
            <p className="text-xs text-muted-stitch mt-3 mb-1">Test card: <span className="font-mono-stitch">4111 1111 1111 1111</span> · expiry <span className="font-mono-stitch">10/29</span> · any CVV</p>
          )}

          <div className="space-y-3 mt-4">
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-semibold text-muted-stitch">Amount ({config.currency || "USD"})</label>
                <input data-testid="payments-amount" type="number" step="0.01" min="0" value={amount} onChange={(e) => setAmount(e.target.value)} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
              </div>
              <div className="flex-1">
                <label className="text-xs font-semibold text-muted-stitch">Customer email</label>
                <input data-testid="payments-email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="optional" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Description</label>
              <input data-testid="payments-description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="optional" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>

            {config.configured ? (
              <div className="neu-pressed rounded-2xl p-4 bg-white" data-testid="payments-widget" style={{ background: "#ffffff" }}>
                <NmiPayments
                  tokenizationKey={config.tokenization_key}
                  payButtonText={`Charge ${fmtMoney(amount)}`}
                  onPay={handlePay}
                />
              </div>
            ) : (
              <p className="text-sm text-muted-stitch">Configure NMI keys to enable the card form.</p>
            )}

            <p className="text-[11px] text-muted-stitch flex items-center gap-1.5 justify-center"><ShieldCheck className="w-3.5 h-3.5" /> Card data is tokenized by NMI — it never touches this server.</p>
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
                    </p>
                    <p className="text-xs text-muted-stitch truncate">
                      {t.email || t.description || t.nmi_transaction_id}{t.response_text ? ` · ${t.response_text}` : ""}
                    </p>
                  </div>
                  <span className="text-[11px] text-muted-stitch shrink-0 hidden sm:block">{new Date(t.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                  <span className="text-[11px] font-bold uppercase px-2 py-1 rounded-full shrink-0" style={{ color: "#fff", background: statusColor[t.status] || "#6b7280" }}>{t.status}</span>
                  {t.type === "sale" && t.status === "success" && !t.refunded && (
                    <button data-testid="payments-refund-btn" onClick={() => refund(t)} title="Refund" className="neu-btn rounded-xl px-2.5 py-2 text-red-500 shrink-0"><RotateCcw className="w-4 h-4" /></button>
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
