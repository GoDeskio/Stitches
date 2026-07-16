import { useState, useEffect } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";
import { Contact2 } from "lucide-react";

export function CrmTab() {
  const [stats, setStats] = useState(null);
  const [data, setData] = useState(null);
  const [type, setType] = useState("");
  const [stage, setStage] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [view, setView] = useState("list");
  const [board, setBoard] = useState(null);
  const [dragId, setDragId] = useState(null);

  const loadStats = () => api.get("/admin/crm/stats").then(({ data }) => setStats(data)).catch(() => {});
  const loadList = () => api.get("/admin/crm/contacts", { params: { type: type || undefined, stage: stage || undefined, q: q || undefined, page } })
    .then(({ data }) => setData(data)).catch(() => {});
  const loadBoard = () => api.get("/admin/crm/board").then(({ data }) => setBoard(data)).catch(() => {});
  useEffect(() => { loadStats(); }, []);
  useEffect(() => { if (view === "list") loadList(); else loadBoard(); }, [type, stage, q, page, view]);

  const moveStage = async (contactId, toStage) => {
    setDragId(null);
    try { await api.put(`/admin/crm/contacts/${contactId}`, { stage: toStage }); loadBoard(); loadStats(); }
    catch (e) { toast.error("Move failed"); }
  };

  const syncUsers = async () => {
    setSyncing(true);
    try { const { data } = await api.post("/admin/crm/sync-users"); toast.success(`Synced ${data.added} new user(s)`); loadStats(); loadList(); }
    catch (e) { toast.error("Sync failed"); } finally { setSyncing(false); }
  };

  const funnel = stats ? [
    { label: "Visitors", val: stats.visitors, sub: "last 30d" },
    { label: "Leads", val: stats.leads, sub: `+${stats.new_leads_week || 0} this week` },
    { label: "Users", val: stats.users, sub: "" },
    { label: "Customers", val: stats.customers, sub: `${stats.lead_to_customer}% of leads` },
  ] : [];

  const stageColor = { new: "#6b7280", contacted: "#3b82f6", qualified: "#8b5cf6", proposal: "#f59e0b", won: "#16a34a", lost: "#ef4444" };

  return (
    <div className="space-y-6" data-testid="crm-tab">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {funnel.map((f, i) => (
          <div key={i} data-testid={`crm-funnel-${f.label.toLowerCase()}`} className="neu-raised rounded-[1.5rem] p-5 animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
            <p className="text-xs text-muted-stitch">{f.label}</p>
            <p className="text-3xl font-head font-bold mt-1" style={{ color: "var(--text)" }}>{f.val}</p>
            {f.sub && <p className="text-xs text-muted-stitch mt-1">{f.sub}</p>}
          </div>
        ))}
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
          <div className="flex items-center gap-3">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Contact2 className="w-5 h-5 text-primary-stitch" /></div>
            <div>
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Contacts</h3>
              <p className="text-sm text-muted-stitch">Manage leads, users and visitors in one pipeline.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="neu-pressed rounded-2xl p-1 flex">
              <button data-testid="crm-view-list" onClick={() => setView("list")} className={`rounded-xl px-3 py-1.5 text-xs font-semibold ${view === "list" ? "neu-primary" : "text-muted-stitch"}`}>List</button>
              <button data-testid="crm-view-pipeline" onClick={() => setView("pipeline")} className={`rounded-xl px-3 py-1.5 text-xs font-semibold ${view === "pipeline" ? "neu-primary" : "text-muted-stitch"}`}>Pipeline</button>
            </div>
            <button data-testid="crm-sync-users-btn" onClick={syncUsers} disabled={syncing} className="neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold text-primary-stitch">{syncing ? "Syncing…" : "Sync users"}</button>
            <button data-testid="crm-add-lead-btn" onClick={() => setShowAdd(true)} className="neu-primary rounded-2xl px-4 py-2.5 text-sm font-semibold">+ Add lead</button>
          </div>
        </div>

        {view === "list" && (
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <input data-testid="crm-search" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} placeholder="Search name, email, company…" className="neu-input rounded-2xl py-2.5 px-4 text-sm flex-1 min-w-[200px]" />
          <select data-testid="crm-filter-type" value={type} onChange={(e) => { setPage(1); setType(e.target.value); }} className="neu-input rounded-2xl py-2.5 px-4 text-sm">
            <option value="">All types</option>
            <option value="lead">Leads</option>
            <option value="user">Users</option>
            <option value="visitor">Visitors</option>
          </select>
          <select data-testid="crm-filter-stage" value={stage} onChange={(e) => { setPage(1); setStage(e.target.value); }} className="neu-input rounded-2xl py-2.5 px-4 text-sm">
            <option value="">All stages</option>
            {CRM_STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        )}

        {view === "pipeline" ? (
          !board ? <Loader /> : (
            <div className="flex gap-3 overflow-x-auto pb-2" data-testid="crm-pipeline">
              {board.stages.map((s) => (
                <div key={s} data-testid={`crm-column-${s}`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => dragId && moveStage(dragId, s)}
                  className="shrink-0 w-56 neu-pressed rounded-2xl p-3">
                  <div className="flex items-center justify-between mb-2 px-1">
                    <span className="text-xs font-bold uppercase" style={{ color: stageColor[s] }}>{s}</span>
                    <span className="text-xs text-muted-stitch">{board.board[s].length}</span>
                  </div>
                  <div className="space-y-2 min-h-[40px]">
                    {board.board[s].map((c) => (
                      <div key={c.contact_id} data-testid="crm-card" draggable
                        onDragStart={() => setDragId(c.contact_id)} onDragEnd={() => setDragId(null)}
                        onClick={() => setSelected(c)}
                        className="neu-raised rounded-xl p-3 cursor-grab active:cursor-grabbing hover:opacity-90 transition-opacity">
                        <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{c.name || c.email}</p>
                        <p className="text-xs text-muted-stitch truncate">{c.company || c.email}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )
        ) : !data ? <Loader /> : data.contacts.length === 0 ? (
          <p className="text-sm text-muted-stitch py-8 text-center">No contacts yet. Add a lead or sync your users to get started.</p>
        ) : (
          <div className="space-y-2">
            {data.contacts.map((c) => (
              <button key={c.contact_id} data-testid="crm-contact-row" onClick={() => setSelected(c)}
                className="w-full neu-pressed rounded-2xl px-4 py-3 flex items-center gap-3 text-left hover:opacity-90 transition-opacity">
                <div className="w-9 h-9 rounded-full neu-sm flex items-center justify-center text-xs font-bold text-primary-stitch shrink-0">{(c.name || c.email || "?").slice(0, 2).toUpperCase()}</div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{c.name || "—"} <span className="text-muted-stitch font-normal">· {c.email}</span></p>
                  <p className="text-xs text-muted-stitch truncate">{c.company || "No company"}{c.source ? ` · via ${c.source}` : ""}</p>
                </div>
                <span className="text-[11px] font-bold uppercase px-2 py-1 rounded-full shrink-0" style={{ color: "#fff", background: stageColor[c.stage] || "#6b7280" }}>{c.stage}</span>
                <span className="text-[11px] text-muted-stitch shrink-0 w-12 text-right">{c.type}</span>
              </button>
            ))}
            {data.pages > 1 && (
              <div className="flex items-center justify-center gap-3 pt-3">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="neu-btn rounded-xl px-4 py-2 text-sm disabled:opacity-40">Prev</button>
                <span className="text-sm text-muted-stitch">{page} / {data.pages}</span>
                <button disabled={page >= data.pages} onClick={() => setPage(page + 1)} className="neu-btn rounded-xl px-4 py-2 text-sm disabled:opacity-40">Next</button>
              </div>
            )}
          </div>
        )}
      </div>

      {showAdd && <CrmAddLead onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); loadStats(); loadList(); loadBoard(); }} />}
      {selected && <CrmContactModal contact={selected} onClose={() => setSelected(null)} onChanged={() => { loadStats(); loadList(); loadBoard(); }} />}
    </div>
  );
}

const CRM_STAGES = ["new", "contacted", "qualified", "proposal", "won", "lost"];

function CrmAddLead({ onClose, onSaved }) {
  const [f, setF] = useState({ name: "", email: "", company: "", phone: "", source: "manual" });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!f.email.trim()) { toast.error("Email required"); return; }
    setSaving(true);
    try { await api.post("/admin/crm/contacts", f); toast.success("Lead added"); onSaved(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } finally { setSaving(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose} data-testid="crm-add-modal">
      <div className="neu-raised rounded-[1.75rem] p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-head font-bold text-xl mb-4" style={{ color: "var(--text)" }}>Add lead</h3>
        <div className="space-y-3">
          <input data-testid="crm-add-name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className="neu-input w-full rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="crm-add-email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="Email *" className="neu-input w-full rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="crm-add-company" value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} placeholder="Company" className="neu-input w-full rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="crm-add-phone" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="Phone" className="neu-input w-full rounded-2xl py-3 px-4 text-sm" />
        </div>
        <div className="flex gap-3 mt-5">
          <button data-testid="crm-add-save" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold flex-1">{saving ? "Saving…" : "Add lead"}</button>
          <button onClick={onClose} className="neu-btn rounded-2xl px-6 py-3 font-semibold">Cancel</button>
        </div>
      </div>
    </div>
  );
}

function CrmContactModal({ contact, onClose, onChanged }) {
  const [c, setC] = useState(contact);
  const [note, setNote] = useState("");
  const saveStage = async (stage) => {
    try { const { data } = await api.put(`/admin/crm/contacts/${c.contact_id}`, { stage }); setC(data); onChanged(); toast.success(`Moved to ${stage}`); }
    catch (e) { toast.error("Failed"); }
  };
  const addNote = async () => {
    if (!note.trim()) return;
    try { const { data } = await api.post(`/admin/crm/contacts/${c.contact_id}/notes`, { text: note }); setC({ ...c, notes: [...(c.notes || []), data] }); setNote(""); onChanged(); }
    catch (e) { toast.error("Failed"); }
  };
  const del = async () => {
    try { await api.delete(`/admin/crm/contacts/${c.contact_id}`); toast.success("Deleted"); onChanged(); onClose(); }
    catch (e) { toast.error("Failed"); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose} data-testid="crm-contact-modal">
      <div className="neu-raised rounded-[1.75rem] p-6 max-w-lg w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{c.name || "—"}</h3>
            <p className="text-sm text-muted-stitch">{c.email}</p>
            <p className="text-xs text-muted-stitch mt-1">{c.company || "No company"}{c.phone ? ` · ${c.phone}` : ""} · {c.type}</p>
          </div>
          <button data-testid="crm-delete-btn" onClick={del} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-red-500">Delete</button>
        </div>

        <p className="text-xs font-semibold text-muted-stitch mt-5 mb-2">Stage</p>
        <div className="flex gap-2 flex-wrap">
          {CRM_STAGES.map((s) => (
            <button key={s} data-testid={`crm-stage-${s}`} onClick={() => saveStage(s)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-all ${c.stage === s ? "neu-primary" : "neu-pressed text-muted-stitch"}`}>{s}</button>
          ))}
        </div>

        <p className="text-xs font-semibold text-muted-stitch mt-5 mb-2">Notes & activity</p>
        <div className="space-y-2 max-h-48 overflow-y-auto mb-3">
          {(c.notes || []).length === 0 ? <p className="text-xs text-muted-stitch">No notes yet.</p> :
            c.notes.map((n, i) => (
              <div key={i} className="neu-pressed rounded-2xl px-4 py-2.5">
                <p className="text-sm" style={{ color: "var(--text)" }}>{n.text}</p>
                <p className="text-xs text-muted-stitch mt-1">{n.author} · {new Date(n.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
              </div>
            ))}
        </div>
        <div className="flex gap-2">
          <input data-testid="crm-note-input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note…" className="neu-input flex-1 rounded-2xl py-2.5 px-4 text-sm" />
          <button data-testid="crm-note-add" onClick={addNote} className="neu-primary rounded-2xl px-4 py-2.5 text-sm font-semibold">Add</button>
        </div>
      </div>
    </div>
  );
}

