import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, Search, CheckCircle2, XCircle, ChevronLeft, ChevronRight, Bot, Download, RotateCw } from "lucide-react";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";

export function BotActionsTab() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(null);

  const load = () => {
    setData(null);
    api.get("/admin/bots/actions", { params: { page, q, status } })
      .then(({ data }) => setData(data)).catch(() => setData({ actions: [], total: 0, pages: 0, page: 1 }));
  };
  useEffect(() => { load(); }, [page, status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const t = setTimeout(() => { setPage(1); load(); }, 350); return () => clearTimeout(t); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const fmt = (iso) => { try { return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); } catch { return ""; } };

  const doExport = async () => {
    try {
      const res = await api.get("/admin/bots/actions/export", { params: { q, status }, responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const link = document.createElement("a");
      link.href = url; link.download = "approval-trail.csv";
      document.body.appendChild(link); link.click(); link.remove();
      URL.revokeObjectURL(url);
      toast.success("Approval trail exported");
    } catch { toast.error("Export failed"); }
  };

  const resend = async (uid) => {
    setBusy(uid);
    try {
      const { data } = await api.post(`/admin/bots/actions/${uid}/resend`);
      toast[data.delivered ? "success" : "error"](data.delivered ? "Callback re-delivered" : `Resend failed (${data.detail || "unreachable"})`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Resend failed"); } finally { setBusy(null); }
  };

  return (
    <div className="animate-fade-up" data-testid="bot-actions-tab">
      <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-6 h-6 text-primary-stitch" />
          <h2 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Approval Trail</h2>
        </div>
        <button data-testid="bot-actions-export" onClick={doExport} className="neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold text-primary-stitch inline-flex items-center gap-2"><Download className="w-4 h-4" /> Export CSV</button>
      </div>
      <p className="text-sm text-muted-stitch mb-5">Every bot-card action taken across the workspace — who approved what, when, and whether the callback to the external tool was delivered.</p>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="neu-pressed rounded-2xl px-3 py-2 flex items-center gap-2 flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-muted-stitch" />
          <input data-testid="bot-actions-search" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search approver, bot, card or action…" className="bg-transparent outline-none text-sm flex-1" style={{ color: "var(--text)" }} />
        </div>
        {["", "delivered", "failed"].map((s) => (
          <button key={s || "all"} data-testid={`bot-actions-filter-${s || "all"}`} onClick={() => { setStatus(s); setPage(1); }}
            className={`neu-btn rounded-full px-3.5 py-2 text-xs font-semibold capitalize ${status === s ? "neu-pressed text-primary-stitch" : "text-muted-stitch"}`}>
            {s || "all"}
          </button>
        ))}
      </div>

      {!data ? <Loader /> : data.actions.length === 0 ? (
        <div className="neu-pressed rounded-[1.75rem] p-10 text-center" data-testid="bot-actions-empty">
          <Bot className="w-10 h-10 text-primary-stitch mx-auto mb-3" />
          <p className="text-sm text-muted-stitch">No card actions recorded yet. When someone taps an Approve/Retry button on a bot card, it shows up here.</p>
        </div>
      ) : (
        <>
          <div className="neu-raised rounded-[1.5rem] overflow-hidden" data-testid="bot-actions-list">
            <div className="hidden md:grid grid-cols-[1.3fr_1fr_1fr_1.2fr_1.1fr_1fr] gap-3 px-5 py-3 text-[11px] uppercase font-bold text-muted-stitch" style={{ background: "var(--neu-dark)" }}>
              <span>Approver</span><span>Bot</span><span>Action</span><span>Card</span><span>Delivered</span><span>When</span>
            </div>
            {data.actions.map((a, i) => (
              <div key={a.action_uid || i} data-testid="bot-action-row" className="grid grid-cols-2 md:grid-cols-[1.3fr_1fr_1fr_1.2fr_1.1fr_1fr] gap-x-3 gap-y-1 px-5 py-3.5 border-t items-center" style={{ borderColor: "var(--neu-dark)" }}>
                <span className="text-sm font-semibold truncate" style={{ color: "var(--text)" }} title={a.user_email}>{a.user_name || "—"}</span>
                <span className="text-sm text-muted-stitch truncate" title={a.bot_name}>{a.bot_name || "—"}</span>
                <span className="text-sm truncate" style={{ color: "var(--text)" }}>{a.action_label || a.action_id}</span>
                <span className="text-sm text-muted-stitch truncate" title={a.card_title}>{a.card_title || "—"}{a.channel_name ? ` · #${a.channel_name}` : ""}</span>
                <span className="text-sm inline-flex items-center gap-2" title={a.detail}>
                  {a.delivered ? <><CheckCircle2 className="w-4 h-4 text-green-500" /> <span className="text-green-500 font-semibold">Yes</span></>
                    : <>
                        <XCircle className="w-4 h-4 text-red-500" /> <span className="text-red-500 font-semibold">No</span>
                        {a.action_uid && (
                          <button data-testid="bot-action-resend" disabled={busy === a.action_uid} onClick={() => resend(a.action_uid)}
                            className="neu-btn rounded-lg px-2 py-1 text-[11px] font-semibold text-primary-stitch inline-flex items-center gap-1 disabled:opacity-50">
                            <RotateCw className={`w-3 h-3 ${busy === a.action_uid ? "animate-spin" : ""}`} /> Resend
                          </button>
                        )}
                      </>}
                  {a.retry_count > 0 && <span className="text-[10px] text-muted-stitch">·{a.retry_count} retry</span>}
                </span>
                <span className="text-xs text-muted-stitch">{fmt(a.created_at)}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mt-4">
            <span className="text-xs text-muted-stitch" data-testid="bot-actions-total">{data.total} action(s) · page {data.page} of {data.pages || 1}</span>
            <div className="flex gap-2">
              <button data-testid="bot-actions-prev" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch disabled:opacity-40"><ChevronLeft className="w-4 h-4" /></button>
              <button data-testid="bot-actions-next" disabled={page >= (data.pages || 1)} onClick={() => setPage((p) => p + 1)} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch disabled:opacity-40"><ChevronRight className="w-4 h-4" /></button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
