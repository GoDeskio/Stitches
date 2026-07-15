import { useEffect, useRef, useState, useCallback } from "react";
import { Plus, Hash, Send, Layers, X, UserPlus, Mail, UserMinus } from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Loader } from "@/components/Stitch";

export default function Messages() {
  const { user } = useAuth();
  const [workspaces, setWorkspaces] = useState(null);
  const [activeWs, setActiveWs] = useState(null);
  const [channels, setChannels] = useState([]);
  const [activeCh, setActiveCh] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [showWsModal, setShowWsModal] = useState(false);
  const [showChModal, setShowChModal] = useState(false);
  const [showMembers, setShowMembers] = useState(false);
  const wsRef = useRef(null);
  const bottomRef = useRef(null);

  const loadWorkspaces = useCallback(async () => {
    const { data } = await api.get("/workspaces");
    setWorkspaces(data);
    if (data.length && !activeWs) setActiveWs(data[0]);
  }, [activeWs]);

  useEffect(() => { loadWorkspaces(); }, []); // eslint-disable-line

  useEffect(() => {
    if (!activeWs) { setChannels([]); return; }
    api.get(`/workspaces/${activeWs.workspace_id}/channels`).then(({ data }) => {
      setChannels(data);
      setActiveCh(data[0] || null);
    });
  }, [activeWs]);

  const loadMessages = useCallback(async (chId) => {
    const { data } = await api.get(`/channels/${chId}/messages`);
    setMessages(data);
  }, []);

  // WebSocket + polling for active channel
  useEffect(() => {
    if (!activeCh) { setMessages([]); return; }
    loadMessages(activeCh.channel_id);

    const token = localStorage.getItem("stitches_token");
    const wsUrl = API.replace(/^http/, "ws") + `/ws/${activeCh.channel_id}?token=${token}`;
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (evt) => {
        const data = JSON.parse(evt.data);
        if (data.type === "message") {
          setMessages((prev) => prev.some((m) => m.message_id === data.message.message_id) ? prev : [...prev, data.message]);
        }
      };
      wsRef.current = ws;
    } catch (e) { /* fallback to polling */ }

    const poll = setInterval(() => loadMessages(activeCh.channel_id), 5000);
    return () => { clearInterval(poll); if (ws) ws.close(); wsRef.current = null; };
  }, [activeCh, loadMessages]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || !activeCh) return;
    setText("");
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ text: t }));
    } else {
      const { data } = await api.post("/messages", { channel_id: activeCh.channel_id, text: t });
      setMessages((prev) => [...prev, data]);
    }
  };

  if (workspaces === null) return <div className="p-10"><Loader /></div>;

  return (
    <div className="flex h-screen">
      {/* Workspace + channels rail */}
      <div className="w-72 shrink-0 p-4 flex flex-col gap-4">
        <div className="neu-raised rounded-3xl p-4 flex-1 flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-3">
            <span className="font-head font-bold text-sm uppercase tracking-widest text-muted-stitch">Workspaces</span>
            <button data-testid="new-workspace-btn" onClick={() => setShowWsModal(true)} className="neu-btn w-8 h-8 rounded-lg flex items-center justify-center text-primary-stitch">
              <Plus className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-2 mb-4">
            {workspaces.map((w) => (
              <button key={w.workspace_id} onClick={() => setActiveWs(w)}
                className={`w-full rounded-xl py-2 px-3 flex items-center gap-2 text-sm font-medium ${activeWs?.workspace_id === w.workspace_id ? "neu-pressed text-primary-stitch" : "text-muted-stitch neu-hover"}`}>
                <Layers className="w-4 h-4 shrink-0" /> <span className="truncate">{w.name}</span>
              </button>
            ))}
            {workspaces.length === 0 && <p className="text-xs text-muted-stitch">No workspaces yet.</p>}
          </div>

          {activeWs && (
            <>
              <div className="flex items-center justify-between mb-3 mt-2">
                <span className="font-head font-bold text-sm uppercase tracking-widest text-muted-stitch">Channels</span>
                <button data-testid="new-channel-btn" onClick={() => setShowChModal(true)} className="neu-btn w-8 h-8 rounded-lg flex items-center justify-center text-primary-stitch">
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-2 overflow-y-auto">
                {channels.map((c) => (
                  <button key={c.channel_id} onClick={() => setActiveCh(c)}
                    className={`w-full rounded-xl py-2 px-3 flex items-center gap-2 text-sm font-medium ${activeCh?.channel_id === c.channel_id ? "neu-pressed text-primary-stitch" : "text-muted-stitch neu-hover"}`}>
                    <Hash className="w-4 h-4 shrink-0" /> <span className="truncate">{c.name}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 p-4 pl-0 min-w-0">
        <div className="neu-raised rounded-3xl h-full flex flex-col overflow-hidden">
          {!activeCh ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-10">
              <div className="neu-raised w-20 h-20 rounded-3xl flex items-center justify-center mb-5">
                <Hash className="w-9 h-9 text-primary-stitch" />
              </div>
              <h3 className="font-head font-bold text-2xl mb-2" style={{ color: "var(--text)" }}>
                {workspaces.length ? "Select a channel" : "Create your first workspace"}
              </h3>
              <p className="text-muted-stitch max-w-sm mb-5">Workspaces hold your channels where your team chats and collaborates in real time.</p>
              {!workspaces.length && (
                <button onClick={() => setShowWsModal(true)} className="neu-primary rounded-2xl px-6 py-3 font-semibold">Create Workspace</button>
              )}
            </div>
          ) : (
            <>
              <div className="p-5 border-b flex items-center gap-3" style={{ borderColor: "var(--border)" }}>
                <Hash className="w-6 h-6 text-primary-stitch" />
                <div>
                  <h2 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{activeCh.name}</h2>
                  <p className="text-xs text-muted-stitch">{activeWs?.name}</p>
                </div>
                <button data-testid="workspace-members-btn" onClick={() => setShowMembers(true)}
                  className="neu-btn ml-auto rounded-xl px-4 py-2 flex items-center gap-2 text-sm font-semibold text-primary-stitch">
                  <UserPlus className="w-4 h-4" /> Members
                </button>
              </div>

              <div className="neu-pressed m-4 rounded-2xl flex-1 overflow-y-auto p-5 space-y-4">
                {messages.length === 0 && <p className="text-center text-muted-stitch py-10">No messages yet. Say hello!</p>}
                {messages.map((m) => {
                  const mine = m.user_id === user?.user_id;
                  return (
                    <div key={m.message_id} className={`flex gap-3 ${mine ? "flex-row-reverse" : ""}`}>
                      <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center shrink-0 overflow-hidden">
                        {m.author_avatar ? <img src={m.author_avatar} alt="" className="w-full h-full object-cover" /> :
                          <span className="font-head font-bold text-sm text-primary-stitch">{(m.author_name || "U")[0]}</span>}
                      </div>
                      <div className={`max-w-[70%] ${mine ? "text-right" : ""}`}>
                        <div className="flex items-center gap-2 mb-1" style={{ flexDirection: mine ? "row-reverse" : "row" }}>
                          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>{m.author_name}</span>
                          <span className="text-xs text-muted-stitch">{new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                        <div className="rounded-2xl px-4 py-2.5 inline-block text-left" style={{ background: mine ? "var(--primary)" : "var(--neu-light)", color: mine ? "#fff" : "var(--text)" }}>
                          {m.text}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={bottomRef} />
              </div>

              <form onSubmit={send} className="p-4 pt-0 flex gap-3">
                <input data-testid="message-input" value={text} onChange={(e) => setText(e.target.value)}
                  placeholder={`Message #${activeCh.name}`} className="neu-input flex-1 rounded-2xl py-3.5 px-5" />
                <button data-testid="send-message-btn" type="submit" className="neu-primary rounded-2xl px-6 flex items-center justify-center">
                  <Send className="w-5 h-5" />
                </button>
              </form>
            </>
          )}
        </div>
      </div>

      {showWsModal && <CreateModal title="New Workspace" placeholder="Workspace name" testid="workspace"
        onClose={() => setShowWsModal(false)} onCreate={async (name) => {
          const { data } = await api.post("/workspaces", { name });
          await loadWorkspaces(); setActiveWs(data); setShowWsModal(false); toast.success("Workspace created");
        }} />}
      {showChModal && <CreateModal title="New Channel" placeholder="channel-name" testid="channel"
        onClose={() => setShowChModal(false)} onCreate={async (name) => {
          const { data } = await api.post("/channels", { workspace_id: activeWs.workspace_id, name });
          setChannels((prev) => [...prev, data]); setActiveCh(data); setShowChModal(false); toast.success("Channel created");
        }} />}
      {showMembers && activeWs && (
        <MembersModal workspace={activeWs} onClose={() => setShowMembers(false)} />
      )}
    </div>
  );
}

function MembersModal({ workspace, onClose }) {
  const [members, setMembers] = useState([]);
  const [email, setEmail] = useState("");
  const [inviting, setInviting] = useState(false);

  const load = useCallback(() => {
    api.get(`/workspaces/${workspace.workspace_id}/members`).then(({ data }) => setMembers(data));
  }, [workspace.workspace_id]);
  useEffect(() => { load(); }, [load]);

  const invite = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setInviting(true);
    try {
      await api.post(`/workspaces/${workspace.workspace_id}/invite`, { email: email.trim() });
      toast.success(`Invited ${email.trim()}`);
      setEmail(""); load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not invite");
    } finally { setInviting(false); }
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

function CreateModal({ title, placeholder, onClose, onCreate, testid }) {
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
