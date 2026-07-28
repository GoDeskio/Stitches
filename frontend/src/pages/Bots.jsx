import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { BACKEND_ORIGIN } from "@/lib/api";
import { PageShell, PageHeader, Loader } from "@/components/Stitch";
import { Bot, Plus, Copy, RefreshCw, Trash2, X, Radio, Users, Share2, GitFork, BookOpen, ChevronDown, Tag, Activity, LayoutTemplate } from "lucide-react";
import { Sparkline } from "@/components/Sparkline";

const INGEST_URL = `${BACKEND_ORIGIN}/api/bots/ingest`;
const CATEGORIES = ["general", "ci", "alerts", "support", "monitoring", "marketing", "sales", "ops"];
const copy = (t, label) => { navigator.clipboard.writeText(t); toast.success(`${label} copied`); };

export default function Bots() {
  const [tab, setTab] = useState("mine");
  const [bots, setBots] = useState(null);
  const [dir, setDir] = useState(null);
  const [creating, setCreating] = useState(false);
  const load = () => api.get("/bots").then(({ data }) => setBots(data.bots)).catch(() => setBots([]));
  const loadDir = () => api.get("/bots/directory").then(({ data }) => setDir(data.bots)).catch(() => setDir([]));
  useEffect(() => { load(); loadDir(); }, []);

  return (
    <PageShell>
      <PageHeader title="Bot Connections" subtitle="Mint a bot token and let any external app, website or tool post into your dashboard chat — BotFather-style." />

      <SetupGuide />

      <div className="flex items-center gap-2 mb-6" data-testid="bots-tabs">
        <button data-testid="bots-tab-mine" onClick={() => setTab("mine")}
          className={`neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold inline-flex items-center gap-2 ${tab === "mine" ? "neu-pressed text-primary-stitch" : "text-muted-stitch"}`}>
          <Bot className="w-4 h-4" /> My bots {bots ? `(${bots.length})` : ""}
        </button>
        <button data-testid="bots-tab-directory" onClick={() => { setTab("directory"); loadDir(); }}
          className={`neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold inline-flex items-center gap-2 ${tab === "directory" ? "neu-pressed text-primary-stitch" : "text-muted-stitch"}`}>
          <Users className="w-4 h-4" /> Directory {dir ? `(${dir.length})` : ""}
        </button>
      </div>

      {tab === "mine" ? (
        <>
          <div className="mb-6">
            <button data-testid="new-bot-btn" onClick={() => setCreating(true)} className="neu-primary rounded-2xl px-5 py-3 font-semibold text-sm inline-flex items-center gap-2"><Plus className="w-4 h-4" /> New bot</button>
          </div>
          {!bots ? <Loader /> : bots.length === 0 ? (
            <div className="neu-pressed rounded-[1.75rem] p-10 text-center animate-fade-up" data-testid="bots-empty">
              <Bot className="w-10 h-10 text-primary-stitch mx-auto mb-3" />
              <p className="text-sm text-muted-stitch">No bots yet. Create one to get a token + an ingest URL your external tools can post to.</p>
            </div>
          ) : (
            <div className="space-y-4" data-testid="bots-list">
              {bots.map((b) => <BotCard key={b.bot_id} bot={b} onChange={() => { load(); loadDir(); }} />)}
            </div>
          )}
        </>
      ) : (
        <Directory dir={dir} onCloned={() => { load(); loadDir(); }} />
      )}

      {creating && <CreateBot onClose={() => setCreating(false)} onDone={() => { load(); loadDir(); }} />}
    </PageShell>
  );
}

function SetupGuide() {
  const [open, setOpen] = useState(false);
  const steps = [
    { n: 1, t: "Create a bot", d: "Click \u201CNew bot\u201D, name it, and pick the channel it should post into." },
    { n: 2, t: "Copy the token", d: "Each bot gets a secret stbot_ token. Copy it — it authenticates your external app." },
    { n: 3, t: "POST a message", d: "Send an HTTP POST to the ingest URL with the token and your text. The message appears in chat instantly." },
    { n: 4, t: "Share & reuse", d: "Flip \u201CShare to directory\u201D so teammates can discover the bot and clone it for their own channels." },
  ];
  return (
    <div className="neu-raised rounded-[1.75rem] p-5 mb-6 animate-fade-up" data-testid="bot-setup-guide">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center justify-between gap-3" data-testid="bot-guide-toggle">
        <span className="flex items-center gap-2 font-head font-bold text-base" style={{ color: "var(--text)" }}>
          <BookOpen className="w-4 h-4 text-primary-stitch" /> How to set up a bot
        </span>
        <ChevronDown className={`w-4 h-4 text-muted-stitch transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2" data-testid="bot-guide-body">
          {steps.map((s) => (
            <div key={s.n} className="neu-pressed rounded-2xl p-4 flex gap-3">
              <div className="neu-sm w-7 h-7 rounded-xl flex items-center justify-center shrink-0 text-primary-stitch font-bold text-sm">{s.n}</div>
              <div>
                <p className="font-semibold text-sm" style={{ color: "var(--text)" }}>{s.t}</p>
                <p className="text-xs text-muted-stitch mt-0.5">{s.d}</p>
              </div>
            </div>
          ))}
          <div className="neu-pressed rounded-2xl p-4 sm:col-span-2">
            <p className="text-xs font-semibold text-muted-stitch mb-1">Ingest endpoint</p>
            <div className="flex items-center gap-2">
              <code className="text-xs font-mono-stitch flex-1 min-w-0 truncate" style={{ color: "var(--text)" }}>{INGEST_URL}</code>
              <button data-testid="guide-copy-url" onClick={() => copy(INGEST_URL, "Ingest URL")} className="neu-btn rounded-lg px-2.5 py-1.5 text-primary-stitch shrink-0"><Copy className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function BotCard({ bot, onChange }) {
  const [showToken, setShowToken] = useState(false);
  const [showCard, setShowCard] = useState(false);
  const curl = `curl -X POST ${INGEST_URL} \\\n  -H "Authorization: Bearer ${bot.token}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"text":"Hello from my app","sender_name":"CI bot"}'`;
  const cardCurl = `curl -X POST ${INGEST_URL} \\\n  -H "Authorization: Bearer ${bot.token}" \\\n  -H "Content-Type: application/json" \\\n  -d '{\n    "card": {\n      "title": "Build #128 passed",\n      "status": "success",\n      "fields": [{"label":"Branch","value":"main"},{"label":"Duration","value":"2m 14s"}],\n      "link": "https://ci.example.com/128"\n    }\n  }'`;
  const patch = async (body, msg) => { try { await api.patch(`/bots/${bot.bot_id}`, body); if (msg) toast.success(msg); onChange(); } catch { toast.error("Failed"); } };
  const toggle = () => patch({ enabled: !bot.enabled });
  const toggleShare = () => patch({ shared: !bot.shared }, bot.shared ? "Removed from directory" : "Shared to directory");
  const rotate = async () => { if (!window.confirm("Rotate this bot's token? The old token stops working immediately.")) return; try { await api.post(`/bots/${bot.bot_id}/rotate`); toast.success("Token rotated"); onChange(); } catch { toast.error("Failed"); } };
  const del = async () => { if (!window.confirm(`Delete bot "${bot.name}"?`)) return; try { await api.delete(`/bots/${bot.bot_id}`); toast.success("Bot deleted"); onChange(); } catch { toast.error("Failed"); } };
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="bot-card">
      <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-3">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Bot className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <p className="font-head font-bold text-lg flex items-center gap-2 flex-wrap" style={{ color: "var(--text)" }}>{bot.name}
              <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${bot.enabled ? "text-green-500" : "text-muted-stitch"}`} style={{ background: "var(--neu-dark)" }}>{bot.enabled ? "active" : "disabled"}</span>
              <select data-testid="bot-category-select" value={bot.category || "general"} onChange={(e) => patch({ category: e.target.value }, "Category updated")}
                className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full text-primary-stitch cursor-pointer border-0 outline-none" style={{ background: "var(--neu-dark)" }}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              {bot.shared && <span data-testid="bot-shared-badge" className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full text-primary-stitch inline-flex items-center gap-1" style={{ background: "var(--neu-dark)" }}><Users className="w-2.5 h-2.5" /> shared</span>}
            </p>
            <p className="text-xs text-muted-stitch flex items-center gap-1.5"><Radio className="w-3 h-3" /> posts to #{bot.target_channel_name || bot.target_channel_id} · {bot.message_count} msg(s)</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex flex-col items-end mr-1">
            <Sparkline data={bot.activity} />
            <span className="text-[10px] text-muted-stitch">14-day activity</span>
          </div>
          <div className="flex gap-2 flex-wrap">
          <button data-testid="bot-share" onClick={toggleShare} className={`neu-btn rounded-xl px-3 py-2 text-xs font-semibold inline-flex items-center gap-1 ${bot.shared ? "text-green-500" : "text-primary-stitch"}`}><Share2 className="w-3.5 h-3.5" /> {bot.shared ? "Shared" : "Share"}</button>
          <button data-testid="bot-toggle" onClick={toggle} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch">{bot.enabled ? "Disable" : "Enable"}</button>
          <button data-testid="bot-rotate" onClick={rotate} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch inline-flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5" /> Rotate</button>
          <button data-testid="bot-delete" onClick={del} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
        </div>
        </div>
      </div>
      <label className="text-xs font-semibold text-muted-stitch">Bot token</label>
      <div className="neu-pressed rounded-2xl px-4 py-3 flex items-center gap-2 mt-1 mb-3">
        <code data-testid="bot-token" className="text-xs font-mono-stitch flex-1 min-w-0 truncate" style={{ color: "var(--text)" }}>{showToken ? bot.token : "stbot_" + "•".repeat(24)}</code>
        <button onClick={() => setShowToken((s) => !s)} className="text-xs text-muted-stitch shrink-0">{showToken ? "Hide" : "Show"}</button>
        <button data-testid="bot-copy-token" onClick={() => copy(bot.token, "Token")} className="neu-btn rounded-lg px-2.5 py-1.5 text-primary-stitch shrink-0"><Copy className="w-3.5 h-3.5" /></button>
      </div>
      <label className="text-xs font-semibold text-muted-stitch">Send a message (any external tool)</label>
      <div className="neu-pressed rounded-2xl p-4 mt-1 relative">
        <pre className="text-[11px] font-mono-stitch overflow-x-auto" style={{ color: "var(--text)" }}>{curl}</pre>
        <button data-testid="bot-copy-curl" onClick={() => copy(curl, "cURL")} className="neu-btn rounded-lg px-2.5 py-1.5 text-primary-stitch absolute top-3 right-3"><Copy className="w-3.5 h-3.5" /></button>
      </div>
      <button data-testid="bot-toggle-card-example" onClick={() => setShowCard((s) => !s)} className="text-xs text-primary-stitch font-semibold mt-2 inline-flex items-center gap-1">
        <LayoutTemplate className="w-3.5 h-3.5" /> {showCard ? "Hide" : "Send a rich card instead"}
      </button>
      {showCard && (
        <div className="neu-pressed rounded-2xl p-4 mt-2 relative" data-testid="bot-card-example">
          <pre className="text-[11px] font-mono-stitch overflow-x-auto" style={{ color: "var(--text)" }}>{cardCurl}</pre>
          <button data-testid="bot-copy-card-curl" onClick={() => copy(cardCurl, "Card cURL")} className="neu-btn rounded-lg px-2.5 py-1.5 text-primary-stitch absolute top-3 right-3"><Copy className="w-3.5 h-3.5" /></button>
        </div>
      )}
    </div>
  );
}

function Directory({ dir, onCloned }) {
  const [cloneTarget, setCloneTarget] = useState(null);
  const [filter, setFilter] = useState("all");
  if (!dir) return <Loader />;
  if (dir.length === 0) return (
    <div className="neu-pressed rounded-[1.75rem] p-10 text-center animate-fade-up" data-testid="directory-empty">
      <Users className="w-10 h-10 text-primary-stitch mx-auto mb-3" />
      <p className="text-sm text-muted-stitch">No shared bots yet. Flip “Share to directory” on any of your bots and teammates can discover &amp; reuse it here.</p>
    </div>
  );
  const cats = Array.from(new Set(dir.map((b) => b.category || "general"))).sort();
  const shown = filter === "all" ? dir : dir.filter((b) => (b.category || "general") === filter);
  return (
    <>
      <div className="flex items-center gap-2 flex-wrap mb-5" data-testid="directory-filters">
        <button data-testid="dir-filter-all" onClick={() => setFilter("all")}
          className={`neu-btn rounded-full px-3.5 py-1.5 text-xs font-semibold inline-flex items-center gap-1 ${filter === "all" ? "neu-pressed text-primary-stitch" : "text-muted-stitch"}`}>
          <Tag className="w-3 h-3" /> All ({dir.length})
        </button>
        {cats.map((c) => (
          <button key={c} data-testid={`dir-filter-${c}`} onClick={() => setFilter(c)}
            className={`neu-btn rounded-full px-3.5 py-1.5 text-xs font-semibold capitalize ${filter === c ? "neu-pressed text-primary-stitch" : "text-muted-stitch"}`}>
            {c} ({dir.filter((b) => (b.category || "general") === c).length})
          </button>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2" data-testid="directory-list">
        {shown.map((b) => (
          <div key={b.bot_id} className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="directory-card">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0"><Bot className="w-5 h-5 text-primary-stitch" /></div>
                <div className="min-w-0">
                  <p className="font-head font-bold text-lg truncate flex items-center gap-2" style={{ color: "var(--text)" }}>{b.name}
                    {b.is_owner && <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full text-muted-stitch shrink-0" style={{ background: "var(--neu-dark)" }}>yours</span>}
                  </p>
                  <p className="text-xs text-muted-stitch truncate">by {b.owner_name} · {b.message_count} msg(s)</p>
                </div>
              </div>
              <span data-testid="directory-category-badge" className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full text-primary-stitch inline-flex items-center gap-1 shrink-0" style={{ background: "var(--neu-dark)" }}><Tag className="w-2.5 h-2.5" /> {b.category || "general"}</span>
            </div>
            {b.description && <p className="text-sm text-muted-stitch mb-3">{b.description}</p>}
            <div className="flex items-center justify-between gap-2 mb-4">
              <p className="text-xs text-muted-stitch flex items-center gap-1.5"><Radio className="w-3 h-3" /> #{b.target_channel_name}</p>
              <span className="flex items-center gap-1.5"><Activity className="w-3 h-3 text-muted-stitch" /><Sparkline data={b.activity} w={80} h={20} /></span>
            </div>
            <button data-testid="directory-clone-btn" onClick={() => setCloneTarget(b)} className="neu-primary rounded-2xl px-4 py-2.5 font-semibold text-sm w-full inline-flex items-center justify-center gap-2"><GitFork className="w-4 h-4" /> Clone & reuse</button>
          </div>
        ))}
      </div>
      {cloneTarget && <CloneBot src={cloneTarget} onClose={() => setCloneTarget(null)} onDone={onCloned} />}
    </>
  );
}

function useWorkspaceChannels() {
  const [workspaces, setWorkspaces] = useState([]);
  const [ws, setWs] = useState("");
  const [channels, setChannels] = useState([]);
  const [channel, setChannel] = useState("");
  useEffect(() => { api.get("/workspaces").then(({ data }) => { setWorkspaces(data); if (data[0]) setWs(data[0].workspace_id); }).catch(() => {}); }, []);
  useEffect(() => {
    if (!ws) return;
    api.get(`/workspaces/${ws}/channels`).then(({ data }) => { setChannels(data); setChannel(data[0]?.channel_id || ""); }).catch(() => setChannels([]));
  }, [ws]);
  return { workspaces, ws, setWs, channels, channel, setChannel };
}

function WsChannelSelects({ hook }) {
  const { workspaces, ws, setWs, channels, channel, setChannel } = hook;
  if (workspaces.length === 0) {
    return (
      <div className="neu-pressed rounded-2xl p-4 mb-5 text-sm text-muted-stitch" data-testid="no-workspace-hint">
        You need a workspace with a channel first. Create or join one from <span className="text-primary-stitch font-semibold">Messages</span>, then come back to add a bot.
      </div>
    );
  }
  return (
    <>
      <label className="text-xs font-semibold text-muted-stitch">Workspace</label>
      <select data-testid="bot-ws-select" value={ws} onChange={(e) => setWs(e.target.value)} className="neu-input w-full rounded-2xl py-2.5 px-3 text-sm mt-1 mb-3">
        {workspaces.map((w) => <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>)}
      </select>
      <label className="text-xs font-semibold text-muted-stitch">Post into channel</label>
      <select data-testid="bot-channel-select" value={channel} onChange={(e) => setChannel(e.target.value)} className="neu-input w-full rounded-2xl py-2.5 px-3 text-sm mt-1 mb-5">
        {channels.map((c) => <option key={c.channel_id} value={c.channel_id}>#{c.name}</option>)}
      </select>
    </>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div className="neu-raised rounded-[1.75rem] p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{title}</h3>
          <button onClick={onClose}><X className="w-5 h-5 text-muted-stitch" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function CreateBot({ onClose, onDone }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("general");
  const [shared, setShared] = useState(false);
  const [busy, setBusy] = useState(false);
  const hook = useWorkspaceChannels();

  const create = async () => {
    if (!name.trim() || !hook.channel) { toast.error("Name and channel required"); return; }
    setBusy(true);
    try { await api.post("/bots", { name: name.trim(), target_channel_id: hook.channel, description: description.trim(), category, shared }); toast.success("Bot created"); onDone(); onClose(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Create failed"); } finally { setBusy(false); }
  };

  return (
    <Modal title="New bot" onClose={onClose}>
      <div data-testid="create-bot-modal">
        <label className="text-xs font-semibold text-muted-stitch">Bot name</label>
        <input data-testid="bot-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Deploy Notifier" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 mb-3" />
        <label className="text-xs font-semibold text-muted-stitch">Short description (optional)</label>
        <input data-testid="bot-desc-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What does this bot do?" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 mb-3" />
        <label className="text-xs font-semibold text-muted-stitch">Category</label>
        <div className="flex flex-wrap gap-2 mt-1 mb-3" data-testid="bot-category-picker">
          {CATEGORIES.map((c) => (
            <button key={c} type="button" data-testid={`bot-cat-${c}`} onClick={() => setCategory(c)}
              className={`neu-btn rounded-full px-3 py-1.5 text-xs font-semibold capitalize ${category === c ? "neu-pressed text-primary-stitch" : "text-muted-stitch"}`}>{c}</button>
          ))}
        </div>
        <WsChannelSelects hook={hook} />
        <label className="flex items-center gap-2 mb-5 cursor-pointer">
          <input data-testid="bot-share-checkbox" type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} className="accent-current" />
          <span className="text-sm text-muted-stitch">Share to the team directory so others can discover & reuse it</span>
        </label>
        <button data-testid="create-bot-submit" onClick={create} disabled={busy} className="neu-primary rounded-2xl px-6 py-3 font-semibold text-sm w-full">{busy ? "Creating…" : "Create bot & get token"}</button>
      </div>
    </Modal>
  );
}

function CloneBot({ src, onClose, onDone }) {
  const [name, setName] = useState(`${src.name} (copy)`);
  const [busy, setBusy] = useState(false);
  const hook = useWorkspaceChannels();

  const clone = async () => {
    if (!hook.channel) { toast.error("Pick a channel"); return; }
    setBusy(true);
    try { await api.post(`/bots/${src.bot_id}/clone`, { name: name.trim(), target_channel_id: hook.channel }); toast.success("Bot cloned — token ready in \u201CMy bots\u201D"); onDone(); onClose(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Clone failed"); } finally { setBusy(false); }
  };

  return (
    <Modal title={`Clone \u201C${src.name}\u201D`} onClose={onClose}>
      <div data-testid="clone-bot-modal">
        <p className="text-xs text-muted-stitch mb-3">Creates your own copy with a fresh token, pointed at a channel you choose.</p>
        <label className="text-xs font-semibold text-muted-stitch">Bot name</label>
        <input data-testid="clone-name-input" value={name} onChange={(e) => setName(e.target.value)} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 mb-3" />
        <WsChannelSelects hook={hook} />
        <button data-testid="clone-bot-submit" onClick={clone} disabled={busy} className="neu-primary rounded-2xl px-6 py-3 font-semibold text-sm w-full">{busy ? "Cloning…" : "Clone & get my token"}</button>
      </div>
    </Modal>
  );
}
