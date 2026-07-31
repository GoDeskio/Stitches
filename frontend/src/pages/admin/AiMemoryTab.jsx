import { useState, useEffect } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Brain, Trash2, Plus, Search, User, Users, Mail } from "lucide-react";

export function AiMemoryTab() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [items, setItems] = useState([]);
  const [scope, setScope] = useState("");
  const [q, setQ] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newScope, setNewScope] = useState("workspace");
  const [adding, setAdding] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [testing, setTesting] = useState(false);

  const loadCfg = () => api.get("/admin/ai-memory/config").then(({ data }) => setCfg(data)).catch(() => {});
  const loadList = () => api.get("/admin/ai-memory/list", { params: { scope, q } }).then(({ data }) => setItems(data)).catch(() => {});
  useEffect(() => { loadCfg(); }, []);
  useEffect(() => { const t = setTimeout(loadList, 250); return () => clearTimeout(t); }, [scope, q]);

  const save = async () => {
    setSaving(true);
    try { await api.put("/admin/ai-memory/config", cfg); toast.success("Memory settings saved"); loadCfg(); }
    catch (e) { toast.error("Save failed"); } finally { setSaving(false); }
  };

  const add = async () => {
    if (!newContent.trim()) { toast.error("Enter a fact to remember"); return; }
    setAdding(true);
    try { await api.post("/admin/ai-memory", { content: newContent, scope: newScope }); setNewContent(""); toast.success("Memory added"); loadList(); loadCfg(); }
    catch (e) { toast.error("Add failed"); } finally { setAdding(false); }
  };

  const del = async (id) => {
    try { await api.delete(`/admin/ai-memory/${id}`); loadList(); loadCfg(); }
    catch (e) { toast.error("Delete failed"); }
  };

  const clearAll = async (sc) => {
    if (!window.confirm(sc ? `Clear all ${sc} memories?` : "Clear ALL AI memories?")) return;
    try { const { data } = await api.delete("/admin/ai-memory", { params: sc ? { scope: sc } : {} }); toast.success(`Cleared ${data.deleted} memories`); loadList(); loadCfg(); }
    catch (e) { toast.error("Clear failed"); }
  };

  const sendTestDigest = async () => {
    if (!testEmail.trim() || !testEmail.includes("@")) { toast.error("Enter a valid email"); return; }
    setTesting(true);
    try {
      const { data } = await api.post("/admin/ai-memory/digest/test", { email: testEmail.trim() });
      if (data.ok) toast.success(`Test digest sent to ${testEmail}`);
      else toast.error("Email not configured — check Admin → Email settings");
    } catch (e) { toast.error("Send failed"); } finally { setTesting(false); }
  };

  if (!cfg) return null;
  const input = "neu-input rounded-2xl py-3 px-4 text-sm";
  const Toggle = ({ on, onClick, testid }) => (
    <button data-testid={testid} onClick={onClick} className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${on ? "justify-end" : "justify-start"}`} style={{ background: on ? "var(--primary)" : "var(--neu-dark)" }}>
      <span className="w-6 h-6 rounded-full bg-white shadow" />
    </button>
  );

  return (
    <div className="space-y-6" data-testid="ai-memory-tab">
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <div className="flex items-center gap-3 mb-1">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Brain className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>AI Memory Persistence</h3>
            <p className="text-sm text-muted-stitch">Control what the Stitch AI assistant remembers across chats. Facts are auto-distilled from conversations and injected into future replies.</p>
          </div>
        </div>

        <div className="neu-pressed rounded-2xl p-4 flex items-center justify-between mt-4">
          <div className="flex items-center gap-3 min-w-0 pr-3">
            <User className="w-5 h-5 text-primary-stitch shrink-0" />
            <div>
              <span className="font-medium text-sm" style={{ color: "var(--text)" }}>Per-user memory</span>
              <p className="text-xs text-muted-stitch mt-0.5">Each user's assistant remembers their own preferences, roles and context. <span className="text-primary-stitch">{cfg.counts.user} stored</span></p>
            </div>
          </div>
          <Toggle testid="mem-user-toggle" on={cfg.user_enabled} onClick={() => setCfg({ ...cfg, user_enabled: !cfg.user_enabled })} />
        </div>

        <div className="neu-pressed rounded-2xl p-4 flex items-center justify-between mt-3">
          <div className="flex items-center gap-3 min-w-0 pr-3">
            <Users className="w-5 h-5 text-primary-stitch shrink-0" />
            <div>
              <span className="font-medium text-sm" style={{ color: "var(--text)" }}>Shared workspace memory</span>
              <p className="text-xs text-muted-stitch mt-0.5">Team-wide facts every user's assistant can use (projects, tools, policies). <span className="text-primary-stitch">{cfg.counts.workspace} stored</span></p>
            </div>
          </div>
          <Toggle testid="mem-workspace-toggle" on={cfg.workspace_enabled} onClick={() => setCfg({ ...cfg, workspace_enabled: !cfg.workspace_enabled })} />
        </div>

        <div className="grid sm:grid-cols-2 gap-3 mt-4">
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Retention (days)</label>
            <input data-testid="mem-retention" type="number" value={cfg.retention_days} onChange={(e) => setCfg({ ...cfg, retention_days: parseInt(e.target.value) || 0 })} className={`${input} w-full mt-1`} />
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Max items per scope</label>
            <input data-testid="mem-max-items" type="number" value={cfg.max_items} onChange={(e) => setCfg({ ...cfg, max_items: parseInt(e.target.value) || 0 })} className={`${input} w-full mt-1`} />
          </div>
        </div>
        <button data-testid="mem-save-btn" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{saving ? "Saving…" : "Save memory settings"}</button>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="mem-add-card">
        <h3 className="font-head font-bold text-lg mb-3" style={{ color: "var(--text)" }}>Add a memory manually</h3>
        <div className="flex gap-3 flex-wrap">
          <input data-testid="mem-new-content" value={newContent} onChange={(e) => setNewContent(e.target.value)} placeholder="e.g. The team ships releases every second Thursday" className={`${input} flex-1 min-w-[16rem]`} />
          <select data-testid="mem-new-scope" value={newScope} onChange={(e) => setNewScope(e.target.value)} className={input}>
            <option value="workspace">Shared workspace</option>
            <option value="user">My user</option>
          </select>
          <button data-testid="mem-add-btn" onClick={add} disabled={adding} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Plus className="w-4 h-4" />Add</button>
        </div>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="mem-digest-test-card">
        <div className="flex items-center gap-3 mb-1">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Mail className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>Test digest delivery</h3>
            <p className="text-sm text-muted-stitch">Send a one-off sample "What Stitch remembers" email to any address to confirm your email setup works end-to-end.</p>
          </div>
        </div>
        <div className="flex gap-3 flex-wrap mt-3">
          <input data-testid="mem-test-email" value={testEmail} onChange={(e) => setTestEmail(e.target.value)} placeholder="you@company.com" className={`${input} flex-1 min-w-[16rem]`} />
          <button data-testid="mem-test-send-btn" onClick={sendTestDigest} disabled={testing} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Mail className="w-4 h-4" />{testing ? "Sending…" : "Send test digest"}</button>
        </div>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="mem-list-card">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
          <h3 className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>Stored memories</h3>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="neu-pressed rounded-2xl flex items-center gap-2 px-3 py-2">
              <Search className="w-4 h-4 text-muted-stitch" />
              <input data-testid="mem-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="bg-transparent text-sm outline-none" style={{ color: "var(--text)" }} />
            </div>
            <select data-testid="mem-scope-filter" value={scope} onChange={(e) => setScope(e.target.value)} className={input}>
              <option value="">All scopes</option>
              <option value="user">User</option>
              <option value="workspace">Workspace</option>
            </select>
            <button data-testid="mem-clear-all-btn" onClick={() => clearAll(scope || "")} className="neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold text-red-500">Clear {scope || "all"}</button>
          </div>
        </div>
        {items.length === 0 ? (
          <p className="text-sm text-muted-stitch">No memories stored yet. They'll appear here as users chat with the assistant.</p>
        ) : (
          <div className="space-y-2 max-h-[28rem] overflow-y-auto">
            {items.map((m) => (
              <div key={m.mem_id} data-testid="mem-row" className="neu-pressed rounded-2xl px-4 py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm" style={{ color: "var(--text)" }}>{m.content}</p>
                  <p className="text-xs text-muted-stitch mt-0.5">
                    <span className={`font-bold uppercase tracking-wide ${m.scope === "workspace" ? "text-amber-500" : "text-primary-stitch"}`}>{m.scope}</span>
                    {" · "}{new Date(m.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
                <button data-testid="mem-delete-btn" onClick={() => del(m.mem_id)} className="neu-btn rounded-xl p-2.5 text-red-500 shrink-0"><Trash2 className="w-4 h-4" /></button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
