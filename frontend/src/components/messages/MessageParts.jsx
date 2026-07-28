import { useEffect, useState, useCallback } from "react";
import { X, Send, Mail, UserPlus, UserMinus, Smile, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

export function MentionText({ text, light }) {
  if (!text) return null;
  const parts = text.split(/(@\S+|https?:\/\/[^\s]+)/g);
  return (
    <span>
      {parts.map((p, i) => {
        if (/^https?:\/\//.test(p))
          return <a key={i} href={p} target="_blank" rel="noreferrer" className="underline font-semibold break-all" style={{ color: light ? "#fff" : "var(--primary)" }}>{p}</a>;
        if (p.startsWith("@"))
          return <span key={i} className="font-semibold" style={{ color: light ? "#fff" : "var(--primary)" }}>{p}</span>;
        return <span key={i}>{p}</span>;
      })}
    </span>
  );
}

const CARD_COLORS = {
  info: "#6366f1", success: "#22c55e", warn: "#f59e0b", error: "#ef4444",
};
const ACTION_CLASSES = {
  primary: "neu-primary text-white",
  default: "neu-btn text-primary-stitch",
  danger: "neu-btn text-red-500",
};

export function BotMessageCard({ card, botId, messageId }) {
  const [busy, setBusy] = useState(null);
  const [done, setDone] = useState({});
  if (!card) return null;
  const accent = CARD_COLORS[card.status] || CARD_COLORS.info;
  const runAction = async (a) => {
    if (!botId || !messageId) return;
    setBusy(a.id);
    try {
      const { data } = await api.post(`/bots/${botId}/action`, { message_id: messageId, action_id: a.id });
      setDone((d) => ({ ...d, [a.id]: true }));
      toast.success(data.delivered ? `Sent “${a.label}” to the bot` : `“${a.label}” recorded (callback ${data.detail || "unreachable"})`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Action failed");
    } finally { setBusy(null); }
  };
  return (
    <div data-testid="bot-message-card" className="neu-pressed rounded-2xl overflow-hidden mt-1 min-w-[240px] max-w-[360px]"
      style={{ borderLeft: `4px solid ${accent}` }}>
      <div className="p-3.5">
        {card.title && <p data-testid="bot-card-title" className="font-head font-bold text-sm mb-1.5" style={{ color: "var(--text)" }}>{card.title}</p>}
        {card.fields?.length > 0 && (
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mb-2">
            {card.fields.map((f, i) => (
              <div key={i} className="min-w-0">
                <p className="text-[10px] uppercase font-bold text-muted-stitch truncate" title={f.label}>{f.label}</p>
                <p className="text-xs truncate" style={{ color: "var(--text)" }} title={f.value}>{f.value}</p>
              </div>
            ))}
          </div>
        )}
        {card.link && (
          <a data-testid="bot-card-link" href={card.link} target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-xs font-semibold mt-1" style={{ color: accent }}>
            Open <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
        {card.actions?.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3" data-testid="bot-card-actions">
            {card.actions.map((a) => (
              <button key={a.id} data-testid={`bot-card-action-${a.id}`} onClick={() => runAction(a)}
                disabled={busy === a.id || done[a.id]}
                className={`rounded-xl px-3 py-1.5 text-xs font-semibold disabled:opacity-60 ${ACTION_CLASSES[a.style] || ACTION_CLASSES.default}`}>
                {busy === a.id ? "…" : done[a.id] ? `✓ ${a.label}` : a.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function ThreadPanel({ parent, messages, members, user, onReply, onReact, onClose }) {
  const [text, setText] = useState("");
  const [showMentions, setShowMentions] = useState(false);
  const [query, setQuery] = useState("");
  const replies = messages.filter((m) => m.parent_id === parent.message_id);

  const handleType = (v) => {
    setText(v);
    const match = v.match(/@(\S*)$/);
    setShowMentions(!!match && members.length > 0);
    setQuery(match ? match[1].toLowerCase() : "");
  };
  const pick = (m) => { setText((prev) => prev.replace(/@(\S*)$/, "@" + m.name + " ")); setShowMentions(false); };
  const submit = async (e) => { e.preventDefault(); if (!text.trim()) return; await onReply(text); setText(""); setShowMentions(false); };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="neu-raised rounded-3xl w-full max-w-lg animate-fade-up flex flex-col max-h-[85vh]" data-testid="thread-panel">
        <div className="flex items-center justify-between p-6 pb-4 border-b" style={{ borderColor: "var(--border)" }}>
          <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Thread</h3>
          <button onClick={onClose} className="text-muted-stitch"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          <div className="neu-pressed rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>{parent.author_name}</span>
              <span className="text-xs text-muted-stitch">{new Date(parent.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
            </div>
            <p className="text-sm" style={{ color: "var(--text)" }}><MentionText text={parent.text} /></p>
          </div>
          <p className="text-xs uppercase tracking-widest text-muted-stitch">{replies.length} {replies.length === 1 ? "reply" : "replies"}</p>
          {replies.map((r) => (
            <div key={r.message_id} className="flex gap-3" data-testid="thread-reply">
              <div className="neu-sm w-8 h-8 rounded-full flex items-center justify-center shrink-0 overflow-hidden">
                {r.author_avatar ? <img src={r.author_avatar} alt="" className="w-full h-full object-cover" /> :
                  <span className="font-head font-bold text-xs text-primary-stitch">{(r.author_name || "U")[0]}</span>}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>{r.author_name}</span>
                  <span className="text-xs text-muted-stitch">{new Date(r.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
                <div className="rounded-2xl px-4 py-2.5 inline-block text-sm" style={{ background: "var(--neu-light)", color: "var(--text)" }}>
                  <MentionText text={r.text} />
                </div>
              </div>
            </div>
          ))}
        </div>
        <form onSubmit={submit} className="p-4 pt-0 flex gap-3 relative">
          {showMentions && (
            <div className="neu-raised absolute bottom-[4.5rem] left-4 right-24 z-40 rounded-2xl p-2 max-h-48 overflow-y-auto animate-fade-up">
              {members.filter((mem) => (mem.name || "").toLowerCase().includes(query)).slice(0, 6).map((mem) => (
                <button type="button" key={mem.user_id} data-testid="thread-mention-option" onClick={() => pick(mem)}
                  className="w-full neu-hover rounded-xl p-2.5 flex items-center gap-3 text-left">
                  <span className="neu-sm w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-primary-stitch">{(mem.name || "U")[0].toUpperCase()}</span>
                  <span className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{mem.name}</span>
                </button>
              ))}
            </div>
          )}
          <input data-testid="thread-input" value={text} onChange={(e) => handleType(e.target.value)}
            placeholder="Reply in thread… use @ to mention" className="neu-input flex-1 rounded-2xl py-3 px-5" />
          <button data-testid="thread-send-btn" type="submit" className="neu-primary rounded-2xl px-5 flex items-center justify-center">
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
}

export function MembersModal({ workspace, onClose }) {
  const [members, setMembers] = useState([]);
  const [friends, setFriends] = useState([]);
  const [email, setEmail] = useState("");
  const [inviting, setInviting] = useState(false);

  const load = useCallback(() => {
    api.get(`/workspaces/${workspace.workspace_id}/members`).then(({ data }) => setMembers(data));
  }, [workspace.workspace_id]);
  useEffect(() => { load(); api.get("/friends").then(({ data }) => setFriends(data)); }, [load]);

  const inviteEmail = async (target) => {
    await api.post(`/workspaces/${workspace.workspace_id}/invite`, { email: target });
    load();
  };
  const invite = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setInviting(true);
    try {
      await inviteEmail(email.trim());
      toast.success(`Invited ${email.trim()}`);
      setEmail("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not invite");
    } finally { setInviting(false); }
  };
  const quickAdd = async (f) => {
    try { await inviteEmail(f.email); toast.success(`Added ${f.name}`); }
    catch (err) { toast.error(err.response?.data?.detail || "Could not add"); }
  };

  const removeMember = async (uid) => {
    try {
      await api.post(`/workspaces/${workspace.workspace_id}/remove`, { user_id: uid });
      toast.success("Member removed"); load();
    } catch (err) { toast.error(err.response?.data?.detail || "Could not remove"); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="neu-raised rounded-3xl p-8 w-full max-w-md animate-fade-up">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Members</h3>
            <p className="text-sm text-muted-stitch">{workspace.name}</p>
          </div>
          <button onClick={onClose} className="text-muted-stitch"><X className="w-5 h-5" /></button>
        </div>

        <form onSubmit={invite} className="flex gap-2 mb-6">
          <div className="relative flex-1">
            <Mail className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-muted-stitch" />
            <input data-testid="invite-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="Invite by email" className="neu-input w-full rounded-2xl py-3 pl-12 pr-4" />
          </div>
          <button data-testid="invite-submit-btn" type="submit" disabled={inviting} className="neu-primary rounded-2xl px-5 font-semibold">
            {inviting ? "…" : "Invite"}
          </button>
        </form>

        {friends.filter((f) => !members.some((m) => m.user_id === f.user_id)).length > 0 && (
          <div className="mb-5">
            <p className="text-xs uppercase tracking-widest text-muted-stitch mb-2">Add from your connections</p>
            <div className="flex flex-wrap gap-2">
              {friends.filter((f) => !members.some((m) => m.user_id === f.user_id)).map((f) => (
                <button key={f.user_id} data-testid="quick-add-friend" onClick={() => quickAdd(f)}
                  className="neu-btn rounded-full pl-2 pr-3 py-1.5 flex items-center gap-2 text-sm">
                  <span className="neu-sm w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-primary-stitch">{(f.name || "U")[0].toUpperCase()}</span>
                  <span style={{ color: "var(--text)" }}>{f.name}</span>
                  <UserPlus className="w-3.5 h-3.5 text-primary-stitch" />
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-2 max-h-72 overflow-y-auto">
          {members.map((m) => (
            <div key={m.user_id} className="neu-pressed rounded-2xl p-3 flex items-center gap-3">
              <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center overflow-hidden shrink-0">
                {m.avatar ? <img src={m.avatar} alt="" className="w-full h-full object-cover" /> :
                  <span className="font-head font-bold text-sm text-primary-stitch">{(m.name || "U")[0].toUpperCase()}</span>}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{m.name} {m.is_owner && <span className="text-xs text-muted-stitch">(owner)</span>}</p>
                <p className="text-xs text-muted-stitch truncate">{m.email}</p>
              </div>
              {!m.is_owner && (
                <button data-testid="remove-member-btn" onClick={() => removeMember(m.user_id)} className="neu-btn w-8 h-8 rounded-lg flex items-center justify-center text-muted-stitch"><UserMinus className="w-4 h-4" /></button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function CreateModal({ title, placeholder, onClose, onCreate, testid }) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!value.trim()) return;
    setLoading(true);
    try { await onCreate(value.trim()); } catch (err) { toast.error("Failed"); } finally { setLoading(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="neu-raised rounded-3xl p-8 w-full max-w-md animate-fade-up">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>{title}</h3>
          <button type="button" onClick={onClose} className="text-muted-stitch"><X className="w-5 h-5" /></button>
        </div>
        <input data-testid={`${testid}-name-input`} autoFocus value={value} onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder} className="neu-input w-full rounded-2xl py-3.5 px-5 mb-6" />
        <button data-testid={`create-${testid}-submit`} type="submit" disabled={loading} className="neu-primary w-full rounded-2xl py-3.5 font-semibold">
          {loading ? "Creating..." : "Create"}
        </button>
      </form>
    </div>
  );
}

const REACT_EMOJIS = ["👍", "❤️", "😂", "🎉", "🙌", "👀"];

export function ReactionPicker({ onPick }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button data-testid="react-btn" onClick={() => setOpen((o) => !o)}
        className="neu-btn w-7 h-7 rounded-full flex items-center justify-center text-muted-stitch opacity-0 group-hover:opacity-100 transition-opacity">
        <Smile className="w-4 h-4" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="neu-raised absolute z-50 bottom-9 left-0 rounded-full p-1.5 flex gap-1 animate-fade-up">
            {REACT_EMOJIS.map((e) => (
              <button key={e} data-testid="react-option" onClick={() => { onPick(e); setOpen(false); }}
                className="w-8 h-8 rounded-full hover:neu-pressed text-lg flex items-center justify-center transition-all">
                {e}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
