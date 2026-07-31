import { useState, useRef, useEffect } from "react";
import { Sparkles, Send, User, Zap, Brain, Trash2, X, Users, Pin, Search, Pencil, Check } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, PageHeader } from "@/components/Stitch";
import { useAuth } from "@/context/AuthContext";

const MODELS = [
  { label: "GPT-5.4", provider: "openai", model: "gpt-5.4" },
  { label: "Claude Sonnet 4.6", provider: "anthropic", model: "claude-sonnet-4-6" },
  { label: "Gemini 3.1 Pro", provider: "gemini", model: "gemini-3.1-pro-preview" },
];

const SUGGESTIONS = [
  "Create a project called Q3 Launch",
  "Create a workspace called Design Studio",
  "Show my dashboard stats",
];

const CAT_META = {
  preference: { label: "Preferences", color: "#8b5cf6" },
  project: { label: "Projects", color: "#3b82f6" },
  deadline: { label: "Deadlines", color: "#f59e0b" },
  tool: { label: "Tools", color: "#10b981" },
  general: { label: "General", color: "#9ca3af" },
};
const CAT_ORDER = ["preference", "project", "deadline", "tool", "general"];

function MemoryPanel({ open, onClose }) {
  const [data, setData] = useState(null);
  const [pinText, setPinText] = useState("");
  const [pinning, setPinning] = useState(false);
  const [query, setQuery] = useState("");
  const [editId, setEditId] = useState(null);
  const [editText, setEditText] = useState("");
  const load = () => api.get("/ai/memory").then(({ data }) => setData(data)).catch(() => setData({ user_enabled: false, workspace_enabled: false, auto_capture: true, user: [], workspace: [] }));
  useEffect(() => { if (open) load(); }, [open]);
  const forget = async (id) => {
    try { await api.delete(`/ai/memory/${id}`); toast.success("Forgotten"); load(); }
    catch (e) { toast.error("Couldn't forget that"); }
  };
  const startEdit = (m) => { setEditId(m.mem_id); setEditText(m.content); };
  const saveEdit = async (id) => {
    if (!editText.trim()) return;
    try { await api.patch(`/ai/memory/${id}`, { content: editText }); setEditId(null); toast.success("Memory updated"); load(); }
    catch (e) { toast.error("Couldn't update that"); }
  };
  const toggleAuto = async () => {
    const next = !data.auto_capture;
    setData({ ...data, auto_capture: next });
    try { await api.put("/ai/memory/prefs", { auto_capture: next }); toast.success(next ? "Stitch will auto-learn new facts" : "Auto-learning off — only pinned memories are kept"); }
    catch (e) { toast.error("Couldn't update"); load(); }
  };
  const pin = async () => {
    if (!pinText.trim()) return;
    setPinning(true);
    try { await api.post("/ai/memory", { content: pinText }); setPinText(""); toast.success("Pinned — Stitch will remember this"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Couldn't pin that"); } finally { setPinning(false); }
  };
  if (!open) return null;
  const q = query.trim().toLowerCase();
  const matches = (m) => !q || m.content.toLowerCase().includes(q);
  const userList = data ? data.user.filter(matches) : [];
  const wsList = data ? data.workspace.filter(matches) : [];
  const nothing = data && data.user.length === 0 && data.workspace.length === 0;
  const noMatches = data && !nothing && userList.length === 0 && wsList.length === 0;

  const renderRow = (m) => (
    <div key={m.mem_id} data-testid="my-memory-row" className="neu-pressed rounded-2xl px-4 py-3">
      {editId === m.mem_id ? (
        <div className="flex gap-2 items-center" data-testid="memory-edit-row">
          <input data-testid="memory-edit-input" value={editText} onChange={(e) => setEditText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") saveEdit(m.mem_id); if (e.key === "Escape") setEditId(null); }}
            autoFocus className="neu-input flex-1 rounded-xl py-2 px-3 text-sm" />
          <button data-testid="memory-edit-save" onClick={() => saveEdit(m.mem_id)} className="neu-primary rounded-xl p-2 shrink-0"><Check className="w-4 h-4" /></button>
          <button data-testid="memory-edit-cancel" onClick={() => setEditId(null)} className="neu-btn rounded-xl p-2 text-muted-stitch shrink-0"><X className="w-4 h-4" /></button>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm flex items-center gap-1.5" style={{ color: "var(--text)" }}>
              {m.source === "pinned" && <Pin className="w-3 h-3 text-primary-stitch shrink-0" />}{m.content}
            </p>
            <p className="text-[11px] text-muted-stitch mt-0.5">{m.source === "pinned" ? "Pinned by you · " : m.source === "suggested" ? "Suggested · " : ""}{m.edited_at ? "edited · " : ""}{new Date(m.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}</p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button data-testid="my-memory-edit" onClick={() => startEdit(m)} title="Edit" className="neu-btn rounded-xl p-2.5 text-primary-stitch"><Pencil className="w-4 h-4" /></button>
            <button data-testid="my-memory-forget" onClick={() => forget(m.mem_id)} title="Forget this" className="neu-btn rounded-xl p-2.5 text-red-500"><Trash2 className="w-4 h-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="memory-panel">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md h-full neu-raised overflow-y-auto p-6 animate-fade-up" style={{ background: "var(--surface)" }}>
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-3">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Brain className="w-5 h-5 text-primary-stitch" /></div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>What Stitch remembers</h3>
          </div>
          <button data-testid="memory-panel-close" onClick={onClose} className="neu-btn rounded-xl p-2.5 text-muted-stitch"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-sm text-muted-stitch mb-5">Stitch uses these facts to personalise its replies. You're always in control — forget anything anytime.</p>

        {!data ? (
          <p className="text-sm text-muted-stitch">Loading…</p>
        ) : !data.user_enabled && !data.workspace_enabled ? (
          <div className="neu-pressed rounded-2xl p-4 text-sm text-muted-stitch">Memory is currently turned off by your admin. Stitch won't remember anything between chats.</div>
        ) : (
          <>
            {data.user_enabled && (
              <div className="neu-pressed rounded-2xl p-4 flex items-center justify-between gap-3 mb-4" data-testid="auto-capture-card">
                <div className="min-w-0 pr-2">
                  <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Let Stitch auto-learn</p>
                  <p className="text-xs text-muted-stitch mt-0.5">{data.auto_capture ? "Stitch picks up new facts from your chats automatically." : "Off — Stitch only remembers what you pin below."}</p>
                </div>
                <button data-testid="auto-capture-toggle" onClick={toggleAuto}
                  className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${data.auto_capture ? "justify-end" : "justify-start"}`}
                  style={{ background: data.auto_capture ? "var(--primary)" : "var(--neu-dark)" }}>
                  <span className="w-6 h-6 rounded-full bg-white shadow" />
                </button>
              </div>
            )}

            {data.user_enabled && (
              <div className="flex gap-2 mb-3" data-testid="pin-memory-row">
                <input data-testid="pin-memory-input" value={pinText} onChange={(e) => setPinText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && pin()} placeholder="Pin something for Stitch to remember…"
                  className="neu-input flex-1 rounded-2xl py-2.5 px-4 text-sm" />
                <button data-testid="pin-memory-btn" onClick={pin} disabled={pinning || !pinText.trim()} className="neu-primary rounded-2xl px-4 font-semibold flex items-center gap-1.5 disabled:opacity-60"><Pin className="w-4 h-4" /></button>
              </div>
            )}

            {!nothing && (
              <div className="neu-pressed rounded-2xl flex items-center gap-2 px-3 py-2 mb-5" data-testid="memory-search-box">
                <Search className="w-4 h-4 text-muted-stitch shrink-0" />
                <input data-testid="memory-search-input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search memories…" className="bg-transparent text-sm outline-none flex-1" style={{ color: "var(--text)" }} />
                {query && <button data-testid="memory-search-clear" onClick={() => setQuery("")} className="text-muted-stitch"><X className="w-3.5 h-3.5" /></button>}
              </div>
            )}

            {nothing ? (
              <div className="neu-pressed rounded-2xl p-4 text-sm text-muted-stitch">Nothing remembered yet. Pin a fact above, or (with auto-learn on) just chat and Stitch will pick up durable facts.</div>
            ) : noMatches ? (
              <div className="neu-pressed rounded-2xl p-4 text-sm text-muted-stitch" data-testid="memory-no-matches">No memories match "{query}".</div>
            ) : (
              <div className="space-y-5">
                {data.user_enabled && (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-primary-stitch mb-2 flex items-center gap-1.5"><User className="w-3.5 h-3.5" /> About you</p>
                    {userList.length === 0 ? <p className="text-xs text-muted-stitch">Nothing here.</p> : (
                      <div className="space-y-4">
                        {CAT_ORDER.filter((c) => userList.some((m) => (m.category || "general") === c)).map((c) => (
                          <div key={c} data-testid={`memory-group-${c}`}>
                            <p className="text-[11px] font-bold uppercase tracking-wide mb-1.5 flex items-center gap-1.5" style={{ color: CAT_META[c].color }}>
                              <span className="w-2 h-2 rounded-full" style={{ background: CAT_META[c].color }} />{CAT_META[c].label}
                            </p>
                            <div className="space-y-2">
                              {userList.filter((m) => (m.category || "general") === c).map(renderRow)}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {data.workspace_enabled && wsList.length > 0 && (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-amber-500 mb-2 flex items-center gap-1.5"><Users className="w-3.5 h-3.5" /> Shared with your team</p>
                    <div className="space-y-2">
                      {wsList.map((m) => (
                        <div key={m.mem_id} data-testid="team-memory-row" className="neu-pressed rounded-2xl px-4 py-3">
                          <p className="text-sm" style={{ color: "var(--text)" }}>{m.content}</p>
                          <p className="text-[11px] text-muted-stitch mt-0.5">Team memory · managed by admins</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function AiAssistant() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState(MODELS[0]);
  const [memOpen, setMemOpen] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy, suggestion]);

  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setSuggestion(null);
    setMessages((prev) => [...prev, { role: "user", content }]);
    setBusy(true);
    try {
      const { data } = await api.post("/ai/agent", { message: content, provider: model.provider, model: model.model });
      const reply = data.reply || "Done.";
      setMessages((prev) => [...prev, { role: "assistant", content: reply, result: data.result, action: data.action }]);
      // Propose a memory (fire-and-forget; only shows if memory is on and a durable fact is found)
      api.post("/ai/memory/suggest", { user_text: content, assistant_text: reply })
        .then(({ data }) => { if (data.suggestion) setSuggestion({ content: data.suggestion, category: data.category }); })
        .catch(() => {});
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, something went wrong reaching the AI." }]);
    } finally { setBusy(false); }
  };

  const acceptSuggestion = async () => {
    if (!suggestion) return;
    try { await api.post("/ai/memory", { content: suggestion.content, category: suggestion.category, source: "suggested" }); toast.success("Stitch will remember this"); }
    catch (e) { toast.error("Couldn't save that"); }
    finally { setSuggestion(null); }
  };

  return (
    <PageShell>
      <PageHeader title="Stitch AI" subtitle="Your built-in AI assistant — ask anything, or tell it to create projects, workspaces, add connections and (as admin) manage the platform."
        action={
          <div className="flex items-center gap-3">
            <button data-testid="open-memory-btn" onClick={() => setMemOpen(true)} className="neu-btn rounded-2xl py-3 px-4 font-medium flex items-center gap-2 text-primary-stitch">
              <Brain className="w-4 h-4" /> Memory
            </button>
            <select data-testid="model-select" value={model.model} onChange={(e) => setModel(MODELS.find((m) => m.model === e.target.value))}
              className="neu-input rounded-2xl py-3 px-4 font-medium cursor-pointer" style={{ color: "var(--text)" }}>
              {MODELS.map((m) => <option key={m.model} value={m.model}>{m.label}</option>)}
            </select>
          </div>
        } />

      <MemoryPanel open={memOpen} onClose={() => setMemOpen(false)} />

      <div className="neu-raised rounded-[1.75rem] flex flex-col" style={{ height: "calc(100vh - 260px)", minHeight: 420 }}>
        <div className="neu-pressed m-4 rounded-2xl flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="neu-raised w-20 h-20 rounded-3xl flex items-center justify-center mb-6"><Sparkles className="w-9 h-9 text-primary-stitch" /></div>
              <h3 className="font-head font-bold text-2xl mb-2" style={{ color: "var(--text)" }}>How can I help you today?</h3>
              <p className="text-muted-stitch mb-6">Try one of these to get started</p>
              <div className="flex flex-col gap-3 w-full max-w-md">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)} className="neu-btn rounded-2xl py-3 px-5 text-sm text-left" style={{ color: "var(--text)" }}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center shrink-0">
                  {m.role === "user" ? <User className="w-4 h-4 text-muted-stitch" /> : <Sparkles className="w-4 h-4 text-primary-stitch" />}
                </div>
                <div className={`max-w-[75%] rounded-2xl px-4 py-3 whitespace-pre-wrap text-[0.95rem] leading-relaxed`}
                  style={{ background: m.role === "user" ? "var(--primary)" : "var(--neu-light)", color: m.role === "user" ? "#fff" : "var(--text)" }}>
                  {m.content}
                  {m.action && m.result?.ok && (
                    <span data-testid="ai-action-chip" className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full" style={{ background: "var(--surface)", color: "var(--primary)" }}>
                      <Zap className="w-3 h-3" /> {m.action.replace(/_/g, " ")}
                    </span>
                  )}
                  {m.result?.items?.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {m.result.items.map((it, k) => <li key={k} className="text-sm opacity-90">• {it}</li>)}
                    </ul>
                  )}
                </div>
              </div>
            ))
          )}
          {busy && (
            <div className="flex gap-3">
              <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center shrink-0"><Sparkles className="w-4 h-4 text-primary-stitch" /></div>
              <div className="rounded-2xl px-4 py-3" style={{ background: "var(--neu-light)" }}>
                <span className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-current animate-bounce text-primary-stitch" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 rounded-full bg-current animate-bounce text-primary-stitch" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 rounded-full bg-current animate-bounce text-primary-stitch" style={{ animationDelay: "300ms" }} />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {suggestion && (
          <div data-testid="memory-suggestion" className="mx-4 mb-3 neu-pressed rounded-2xl px-4 py-3 flex items-center gap-3 animate-fade-up">
            <Brain className="w-5 h-5 text-primary-stitch shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-xs text-muted-stitch">Want Stitch to remember this?</p>
              <p className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>{suggestion.content}</p>
            </div>
            <button data-testid="suggestion-accept" onClick={acceptSuggestion} className="neu-primary rounded-xl px-3 py-2 text-sm font-semibold flex items-center gap-1.5 shrink-0"><Check className="w-4 h-4" /> Remember</button>
            <button data-testid="suggestion-dismiss" onClick={() => setSuggestion(null)} className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold text-muted-stitch shrink-0">Dismiss</button>
          </div>
        )}

        <form onSubmit={(e) => { e.preventDefault(); send(); }} className="p-4 pt-0 flex gap-3">
          <input data-testid="ai-input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Message Stitch AI..."
            className="neu-input flex-1 rounded-2xl py-3.5 px-5" />
          <button data-testid="ai-send-btn" type="submit" disabled={busy} className="neu-primary rounded-2xl px-6 flex items-center justify-center disabled:opacity-70">
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </PageShell>
  );
}
