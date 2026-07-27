import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { BACKEND_ORIGIN } from "@/lib/api";
import { PageShell, PageHeader, Loader } from "@/components/Stitch";
import { Bot, Plus, Copy, RefreshCw, Trash2, X, Radio } from "lucide-react";

const INGEST_URL = `${BACKEND_ORIGIN}/api/bots/ingest`;
const copy = (t, label) => { navigator.clipboard.writeText(t); toast.success(`${label} copied`); };

export default function Bots() {
  const [bots, setBots] = useState(null);
  const [creating, setCreating] = useState(false);
  const load = () => api.get("/bots").then(({ data }) => setBots(data.bots)).catch(() => setBots([]));
  useEffect(() => { load(); }, []);
  return (
    <PageShell>
      <PageHeader title="Bot Connections" subtitle="Mint a bot token and let any external app, website or tool post into your dashboard chat — BotFather-style." />
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
          {bots.map((b) => <BotCard key={b.bot_id} bot={b} onChange={load} />)}
        </div>
      )}
      {creating && <CreateBot onClose={() => setCreating(false)} onDone={load} />}
    </PageShell>
  );
}

function BotCard({ bot, onChange }) {
  const [showToken, setShowToken] = useState(false);
  const curl = `curl -X POST ${INGEST_URL} \\\n  -H "Authorization: Bearer ${bot.token}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"text":"Hello from my app","sender_name":"CI bot"}'`;
  const toggle = async () => { try { await api.patch(`/bots/${bot.bot_id}`, { enabled: !bot.enabled }); onChange(); } catch { toast.error("Failed"); } };
  const rotate = async () => { if (!window.confirm("Rotate this bot's token? The old token stops working immediately.")) return; try { await api.post(`/bots/${bot.bot_id}/rotate`); toast.success("Token rotated"); onChange(); } catch { toast.error("Failed"); } };
  const del = async () => { if (!window.confirm(`Delete bot "${bot.name}"?`)) return; try { await api.delete(`/bots/${bot.bot_id}`); toast.success("Bot deleted"); onChange(); } catch { toast.error("Failed"); } };
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="bot-card">
      <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-3">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Bot className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <p className="font-head font-bold text-lg flex items-center gap-2" style={{ color: "var(--text)" }}>{bot.name}
              <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${bot.enabled ? "text-green-500" : "text-muted-stitch"}`} style={{ background: "var(--neu-dark)" }}>{bot.enabled ? "active" : "disabled"}</span>
            </p>
            <p className="text-xs text-muted-stitch flex items-center gap-1.5"><Radio className="w-3 h-3" /> posts to #{bot.target_channel_name || bot.target_channel_id} · {bot.message_count} msg(s)</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button data-testid="bot-toggle" onClick={toggle} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch">{bot.enabled ? "Disable" : "Enable"}</button>
          <button data-testid="bot-rotate" onClick={rotate} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch inline-flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5" /> Rotate</button>
          <button data-testid="bot-delete" onClick={del} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
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
    </div>
  );
}

function CreateBot({ onClose, onDone }) {
  const [name, setName] = useState("");
  const [workspaces, setWorkspaces] = useState([]);
  const [ws, setWs] = useState("");
  const [channels, setChannels] = useState([]);
  const [channel, setChannel] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/workspaces").then(({ data }) => { setWorkspaces(data); if (data[0]) setWs(data[0].workspace_id); }).catch(() => {}); }, []);
  useEffect(() => {
    if (!ws) return;
    api.get(`/workspaces/${ws}/channels`).then(({ data }) => { setChannels(data); setChannel(data[0]?.channel_id || ""); }).catch(() => setChannels([]));
  }, [ws]);

  const create = async () => {
    if (!name.trim() || !channel) { toast.error("Name and channel required"); return; }
    setBusy(true);
    try { await api.post("/bots", { name: name.trim(), target_channel_id: channel }); toast.success("Bot created"); onDone(); onClose(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Create failed"); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose} data-testid="create-bot-modal">
      <div className="neu-raised rounded-[1.75rem] p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>New bot</h3>
          <button onClick={onClose}><X className="w-5 h-5 text-muted-stitch" /></button>
        </div>
        <label className="text-xs font-semibold text-muted-stitch">Bot name</label>
        <input data-testid="bot-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Deploy Notifier" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 mb-3" />
        <label className="text-xs font-semibold text-muted-stitch">Workspace</label>
        <select data-testid="bot-ws-select" value={ws} onChange={(e) => setWs(e.target.value)} className="neu-input w-full rounded-2xl py-2.5 px-3 text-sm mt-1 mb-3">
          {workspaces.map((w) => <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>)}
        </select>
        <label className="text-xs font-semibold text-muted-stitch">Post into channel</label>
        <select data-testid="bot-channel-select" value={channel} onChange={(e) => setChannel(e.target.value)} className="neu-input w-full rounded-2xl py-2.5 px-3 text-sm mt-1 mb-5">
          {channels.map((c) => <option key={c.channel_id} value={c.channel_id}>#{c.name}</option>)}
        </select>
        <button data-testid="create-bot-submit" onClick={create} disabled={busy} className="neu-primary rounded-2xl px-6 py-3 font-semibold text-sm w-full">{busy ? "Creating…" : "Create bot & get token"}</button>
      </div>
    </div>
  );
}
