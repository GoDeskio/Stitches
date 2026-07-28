import { useEffect, useRef, useState, useCallback } from "react";
import { Plus, Hash, Send, Layers, X, UserPlus, Mail, UserMinus, MessageSquare, Smile, AtSign, CornerDownRight, Video } from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Loader } from "@/components/Stitch";
import { MentionText, ThreadPanel, MembersModal, CreateModal, ReactionPicker, BotMessageCard } from "@/components/messages/MessageParts";

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
  const [mode, setMode] = useState("channels");
  const [dms, setDms] = useState([]);
  const [friends, setFriends] = useState([]);
  const [showDmPicker, setShowDmPicker] = useState(false);
  const [unreads, setUnreads] = useState({ channels: {}, total: 0 });
  const [typingName, setTypingName] = useState(null);
  const [members, setMembers] = useState([]);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [threadParent, setThreadParent] = useState(null);
  const typingSentRef = useRef(0);
  const typingTimerRef = useRef(null);
  const wsRef = useRef(null);
  const bottomRef = useRef(null);
  const skipScrollRef = useRef(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const PAGE = 50;

  const loadWorkspaces = useCallback(async () => {
    const { data } = await api.get("/workspaces");
    setWorkspaces(data);
    if (data.length && !activeWs) setActiveWs(data[0]);
  }, [activeWs]);

  useEffect(() => { loadWorkspaces(); }, []); // eslint-disable-line

  useEffect(() => {
    if (!activeWs) { setChannels([]); setMembers([]); return; }
    api.get(`/workspaces/${activeWs.workspace_id}/channels`).then(({ data }) => {
      setChannels(data);
      setActiveCh(data[0] || null);
    });
    api.get(`/workspaces/${activeWs.workspace_id}/members`).then(({ data }) => setMembers(data)).catch(() => setMembers([]));
  }, [activeWs]);

  const loadMessages = useCallback(async (chId) => {
    const { data } = await api.get(`/channels/${chId}/messages?limit=${PAGE}`);
    setMessages(data);
    setHasMore(data.length === PAGE);
  }, []);

  const mergeMessages = (prev, incoming) => {
    const map = new Map();
    incoming.forEach((m) => map.set(m.message_id, m));
    prev.forEach((m) => map.set(m.message_id, m));
    return Array.from(map.values()).sort((a, b) => (a.created_at < b.created_at ? -1 : 1));
  };

  const refreshLatest = useCallback(async (chId) => {
    try {
      const { data } = await api.get(`/channels/${chId}/messages?limit=${PAGE}`);
      setMessages((prev) => mergeMessages(prev, data));
    } catch (e) {}
  }, []);

  const loadEarlier = async () => {
    if (!activeCh || messages.length === 0 || loadingMore) return;
    setLoadingMore(true);
    const oldest = messages.reduce((a, m) => (m.created_at < a ? m.created_at : a), messages[0].created_at);
    try {
      const { data } = await api.get(`/channels/${activeCh.channel_id}/messages?before=${encodeURIComponent(oldest)}&limit=${PAGE}`);
      if (data.length) {
        skipScrollRef.current = true;
        setMessages((prev) => mergeMessages(prev, data));
      }
      setHasMore(data.length === PAGE);
    } catch (e) {} finally { setLoadingMore(false); }
  };

  const loadUnreads = useCallback(async () => {
    try { const { data } = await api.get("/unreads"); setUnreads(data); } catch (e) {}
  }, []);

  useEffect(() => { loadUnreads(); const t = setInterval(loadUnreads, 15000); return () => clearInterval(t); }, [loadUnreads]);

  const markRead = useCallback(async (chId) => {
    try { await api.post(`/channels/${chId}/read`); } catch (e) {}
    setUnreads((prev) => {
      if (!prev.channels[chId]) return prev;
      const channels = { ...prev.channels };
      const removed = channels[chId]; delete channels[chId];
      return { channels, total: Math.max(0, prev.total - removed) };
    });
  }, []);

  // WebSocket + polling for active channel
  useEffect(() => {
    if (!activeCh) { setMessages([]); return; }
    loadMessages(activeCh.channel_id);
    markRead(activeCh.channel_id);
    setTypingName(null);

    const token = localStorage.getItem("stitches_token");
    const wsUrl = API.replace(/^http/, "ws") + `/ws/${activeCh.channel_id}?token=${token}`;
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (evt) => {
        const data = JSON.parse(evt.data);
        if (data.type === "message") {
          setMessages((prev) => prev.some((m) => m.message_id === data.message.message_id) ? prev : [...prev, data.message]);
          if (data.message.user_id !== user?.user_id) markRead(activeCh.channel_id);
        } else if (data.type === "typing" && data.user_id !== user?.user_id) {
          setTypingName(data.user_name);
          clearTimeout(typingTimerRef.current);
          typingTimerRef.current = setTimeout(() => setTypingName(null), 3000);
        } else if (data.type === "reaction") {
          setMessages((prev) => prev.map((mm) => mm.message_id === data.message_id ? { ...mm, reactions: data.reactions } : mm));
        }
      };
      wsRef.current = ws;
    } catch (e) { /* fallback to polling */ }

    const poll = setInterval(() => refreshLatest(activeCh.channel_id), 5000);
    return () => { clearInterval(poll); if (ws) ws.close(); wsRef.current = null; };
  }, [activeCh, loadMessages, refreshLatest, markRead, user]);

  useEffect(() => {
    if (skipScrollRef.current) { skipScrollRef.current = false; return; }
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const extractMentions = (t) => members.filter((m) => m.name && t.includes("@" + m.name)).map((m) => m.user_id);

  const startChannelMeeting = async () => {
    if (!activeCh) return;
    try {
      const { data } = await api.post("/meetings", { name: `${activeCh.name} meeting`, channel_id: activeCh.channel_id });
      window.open(`/call/${data.room_id}`, "_blank", "width=1200,height=820");
      refreshLatest(activeCh.channel_id);
      toast.success("Meeting started — the channel has been notified");
    } catch (err) { toast.error("Could not start meeting"); }
  };

  const send = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || !activeCh) return;
    setText(""); setShowMentions(false);
    const mentions = extractMentions(t);
    const { data } = await api.post("/messages", { channel_id: activeCh.channel_id, text: t, mentions });
    setMessages((prev) => prev.some((m) => m.message_id === data.message_id) ? prev : [...prev, data]);
  };

  const sendReply = async (t) => {
    if (!t.trim() || !activeCh || !threadParent) return;
    const mentions = extractMentions(t);
    const { data } = await api.post("/messages", { channel_id: activeCh.channel_id, text: t.trim(), parent_id: threadParent.message_id, mentions });
    setMessages((prev) => prev.some((m) => m.message_id === data.message_id) ? prev : [...prev, data]);
  };

  const pickMention = (m) => {
    setText((prev) => prev.replace(/@(\S*)$/, "@" + m.name + " "));
    setShowMentions(false);
  };

  const handleType = (v) => {
    setText(v);
    const match = v.match(/@(\S*)$/);
    setShowMentions(!!match && members.length > 0);
    setMentionQuery(match ? match[1].toLowerCase() : "");
    const now = Date.now();
    if (wsRef.current?.readyState === WebSocket.OPEN && now - typingSentRef.current > 2000) {
      typingSentRef.current = now;
      wsRef.current.send(JSON.stringify({ type: "typing" }));
    }
  };

  const react = async (messageId, emoji) => {
    try {
      const { data } = await api.post(`/messages/${messageId}/react`, { emoji });
      setMessages((prev) => prev.map((mm) => mm.message_id === messageId ? { ...mm, reactions: data.reactions } : mm));
    } catch (e) {}
  };

  const loadDms = async () => { const { data } = await api.get("/dms"); setDms(data); };
  const openDirect = async () => {
    setMode("direct");
    loadDms();
    const { data } = await api.get("/friends");
    setFriends(data);
  };
  const selectDm = (d) => {
    setActiveWs(null);
    setActiveCh({ channel_id: d.dm_id, name: d.other?.name || "Direct message", type: "dm", other: d.other });
  };
  const startDm = async (friendId) => {
    const { data } = await api.post("/dms", { user_id: friendId });
    setShowDmPicker(false);
    await loadDms();
    selectDm(data);
  };

  useEffect(() => {
    const pending = localStorage.getItem("stitches_open_dm");
    if (pending) {
      localStorage.removeItem("stitches_open_dm");
      setMode("direct");
      api.get("/friends").then(({ data }) => setFriends(data));
      startDm(pending);
    }
  }, []); // eslint-disable-line

  if (workspaces === null) return <div className="p-10"><Loader /></div>;

  return (
    <div className="flex h-screen">
      {/* Workspace + channels rail */}
      <div className="w-72 shrink-0 p-4 flex flex-col gap-4">
        <div className="neu-raised rounded-3xl p-4 flex-1 flex flex-col min-h-0">
          <div className="neu-pressed rounded-full p-1 flex mb-4">
            <button data-testid="mode-channels" onClick={() => setMode("channels")}
              className={`flex-1 rounded-full py-2 text-xs font-bold uppercase tracking-wider transition-all ${mode === "channels" ? "neu-primary" : "text-muted-stitch"}`}>Channels</button>
            <button data-testid="mode-direct" onClick={openDirect}
              className={`flex-1 rounded-full py-2 text-xs font-bold uppercase tracking-wider transition-all ${mode === "direct" ? "neu-primary" : "text-muted-stitch"}`}>Direct</button>
          </div>

          {mode === "channels" ? (
            <>
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
                      <button key={c.channel_id} data-testid="channel-item" onClick={() => setActiveCh(c)}
                        className={`w-full rounded-xl py-2 px-3 flex items-center gap-2 text-sm font-medium ${activeCh?.channel_id === c.channel_id ? "neu-pressed text-primary-stitch" : "text-muted-stitch neu-hover"}`}>
                        <Hash className="w-4 h-4 shrink-0" /> <span className="truncate flex-1 text-left">{c.name}</span>
                        {unreads.channels[c.channel_id] > 0 && activeCh?.channel_id !== c.channel_id && (
                          <span data-testid="channel-unread" className="min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-bold flex items-center justify-center text-white" style={{ background: "var(--primary)" }}>{unreads.channels[c.channel_id]}</span>
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3">
                <span className="font-head font-bold text-sm uppercase tracking-widest text-muted-stitch">Direct Messages</span>
                <button data-testid="new-dm-btn" onClick={() => setShowDmPicker(true)} className="neu-btn w-8 h-8 rounded-lg flex items-center justify-center text-primary-stitch">
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-2 overflow-y-auto">
                {dms.length === 0 && <p className="text-xs text-muted-stitch">No conversations yet. Start one with a connection.</p>}
                {dms.map((d) => (
                  <button key={d.dm_id} data-testid="dm-item" onClick={() => selectDm(d)}
                    className={`w-full rounded-xl py-2 px-3 flex items-center gap-2 text-sm font-medium ${activeCh?.channel_id === d.dm_id ? "neu-pressed text-primary-stitch" : "text-muted-stitch neu-hover"}`}>
                    <span className="relative shrink-0">
                      <MessageSquare className="w-4 h-4" />
                      {d.other?.online && <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-green-500" />}
                    </span>
                    <span className="truncate flex-1 text-left">{d.other?.name}</span>
                    {unreads.channels[d.dm_id] > 0 && activeCh?.channel_id !== d.dm_id && (
                      <span data-testid="dm-unread" className="min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-bold flex items-center justify-center text-white" style={{ background: "var(--primary)" }}>{unreads.channels[d.dm_id]}</span>
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {showDmPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={() => setShowDmPicker(false)}>
          <div onClick={(e) => e.stopPropagation()} className="neu-raised rounded-3xl p-8 w-full max-w-md animate-fade-up">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>New message</h3>
              <button onClick={() => setShowDmPicker(false)} className="text-muted-stitch"><X className="w-5 h-5" /></button>
            </div>
            <p className="text-sm text-muted-stitch mb-4">Pick a connection to message. Add more people from the People page.</p>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {friends.length === 0 && <p className="text-sm text-muted-stitch">You have no connections yet.</p>}
              {friends.map((f) => (
                <button key={f.user_id} data-testid="dm-friend-option" onClick={() => startDm(f.user_id)}
                  className="w-full neu-hover rounded-2xl p-3 flex items-center gap-3 text-left">
                  <span className="relative neu-sm w-9 h-9 rounded-full flex items-center justify-center overflow-hidden shrink-0">
                    {f.avatar ? <img src={f.avatar} alt="" className="w-full h-full object-cover" /> :
                      <span className="font-head font-bold text-sm text-primary-stitch">{(f.name || "U")[0].toUpperCase()}</span>}
                    {f.online && <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-green-500 border border-[var(--surface)]" />}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{f.name}</p>
                    <p className="text-xs text-muted-stitch truncate">{f.online ? "Online" : "Offline"}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

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
                {activeCh.type === "dm" ? <MessageSquare className="w-6 h-6 text-primary-stitch" /> : <Hash className="w-6 h-6 text-primary-stitch" />}
                <div>
                  <h2 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{activeCh.name}</h2>
                  <p className="text-xs text-muted-stitch flex items-center gap-1.5">
                    {activeCh.type === "dm" ? (
                      <>{activeCh.other?.online && <span className="w-2 h-2 rounded-full bg-green-500" />}{activeCh.other?.online ? "Online" : "Direct message"}</>
                    ) : (activeWs?.name)}
                  </p>
                </div>
                {activeWs && activeCh.type !== "dm" && (
                  <button data-testid="workspace-members-btn" onClick={() => setShowMembers(true)}
                    className="neu-btn ml-auto rounded-xl px-4 py-2 flex items-center gap-2 text-sm font-semibold text-primary-stitch">
                    <UserPlus className="w-4 h-4" /> Members
                  </button>
                )}
                <button data-testid="channel-meet-btn" onClick={startChannelMeeting}
                  className={`neu-primary rounded-xl px-4 py-2 flex items-center gap-2 text-sm font-semibold ${activeWs && activeCh.type !== "dm" ? "" : "ml-auto"}`}>
                  <Video className="w-4 h-4" /> Meet
                </button>
              </div>

              <div className="neu-pressed m-4 rounded-2xl flex-1 overflow-y-auto p-5 space-y-4">
                {hasMore && (
                  <div className="flex justify-center">
                    <button data-testid="load-earlier-btn" onClick={loadEarlier} disabled={loadingMore}
                      className="neu-btn rounded-full px-4 py-1.5 text-xs font-semibold text-primary-stitch">
                      {loadingMore ? "Loading…" : "Load earlier messages"}
                    </button>
                  </div>
                )}
                {messages.filter((m) => !m.parent_id).length === 0 && <p className="text-center text-muted-stitch py-10">No messages yet. Say hello!</p>}
                {messages.filter((m) => !m.parent_id).map((m) => {
                  const mine = m.user_id === user?.user_id;
                  const replyCount = messages.filter((r) => r.parent_id === m.message_id).length;
                  return (
                    <div key={m.message_id} className={`flex gap-3 ${mine ? "flex-row-reverse" : ""}`}>
                      <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center shrink-0 overflow-hidden">
                        {m.author_avatar ? <img src={m.author_avatar} alt="" className="w-full h-full object-cover" /> :
                          <span className="font-head font-bold text-sm text-primary-stitch">{(m.author_name || "U")[0]}</span>}
                      </div>
                      <div className={`max-w-[70%] group ${mine ? "text-right" : ""}`}>
                        <div className="flex items-center gap-2 mb-1" style={{ flexDirection: mine ? "row-reverse" : "row" }}>
                          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>{m.author_name}</span>
                          <span className="text-xs text-muted-stitch">{new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                        <div className={`flex items-center gap-2 ${mine ? "flex-row-reverse" : ""}`}>
                          <div className="rounded-2xl px-4 py-2.5 inline-block text-left" style={{ background: mine ? "var(--primary)" : "var(--neu-light)", color: mine ? "#fff" : "var(--text)" }}>
                            {m.text && <MentionText text={m.text} light={mine} />}
                            {m.card && <BotMessageCard card={m.card} />}
                          </div>
                          <div className={`flex items-center gap-1 ${mine ? "flex-row-reverse" : ""}`}>
                            <ReactionPicker onPick={(e) => react(m.message_id, e)} />
                            <button data-testid="reply-btn" onClick={() => setThreadParent(m)} title="Reply in thread"
                              className="neu-btn w-7 h-7 rounded-full flex items-center justify-center text-muted-stitch opacity-0 group-hover:opacity-100 transition-opacity">
                              <CornerDownRight className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                        {m.reactions && Object.keys(m.reactions).length > 0 && (
                          <div className={`flex flex-wrap gap-1.5 mt-1.5 ${mine ? "justify-end" : ""}`}>
                            {Object.entries(m.reactions).map(([emoji, users]) => (
                              <button key={emoji} data-testid="reaction-chip" onClick={() => react(m.message_id, emoji)}
                                className={`neu-sm rounded-full px-2 py-0.5 text-xs flex items-center gap-1 ${users.includes(user?.user_id) ? "text-primary-stitch" : "text-muted-stitch"}`}>
                                <span>{emoji}</span> <span>{users.length}</span>
                              </button>
                            ))}
                          </div>
                        )}
                        {replyCount > 0 && (
                          <button data-testid="thread-count-btn" onClick={() => setThreadParent(m)}
                            className={`mt-1.5 text-xs font-semibold text-primary-stitch flex items-center gap-1.5 ${mine ? "ml-auto flex-row-reverse" : ""}`}>
                            <MessageSquare className="w-3.5 h-3.5" /> {replyCount} {replyCount === 1 ? "reply" : "replies"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div ref={bottomRef} />
              </div>

              <div className="px-5 h-5 -mt-1 mb-1">
                {typingName && (
                  <span data-testid="typing-indicator" className="text-xs text-primary-stitch flex items-center gap-1.5">
                    <span className="flex gap-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: "300ms" }} />
                    </span>
                    {typingName} is typing…
                  </span>
                )}
              </div>

              <form onSubmit={send} className="p-4 pt-0 flex gap-3 relative">
                {showMentions && (
                  <div data-testid="mention-dropdown" className="neu-raised absolute bottom-[4.5rem] left-4 right-24 z-40 rounded-2xl p-2 max-h-56 overflow-y-auto animate-fade-up">
                    {members.filter((mem) => (mem.name || "").toLowerCase().includes(mentionQuery)).slice(0, 6).map((mem) => (
                      <button type="button" key={mem.user_id} data-testid="mention-option" onClick={() => pickMention(mem)}
                        className="w-full neu-hover rounded-xl p-2.5 flex items-center gap-3 text-left">
                        <span className="neu-sm w-8 h-8 rounded-full flex items-center justify-center overflow-hidden shrink-0">
                          {mem.avatar ? <img src={mem.avatar} alt="" className="w-full h-full object-cover" /> :
                            <span className="font-head font-bold text-xs text-primary-stitch">{(mem.name || "U")[0].toUpperCase()}</span>}
                        </span>
                        <span className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{mem.name}</span>
                        <AtSign className="w-3.5 h-3.5 text-muted-stitch ml-auto" />
                      </button>
                    ))}
                    {members.filter((mem) => (mem.name || "").toLowerCase().includes(mentionQuery)).length === 0 && (
                      <p className="text-xs text-muted-stitch p-2">No members match.</p>
                    )}
                  </div>
                )}
                <input data-testid="message-input" value={text} onChange={(e) => handleType(e.target.value)}
                  placeholder={activeCh.type === "dm" ? `Message ${activeCh.name}` : `Message #${activeCh.name}`} className="neu-input flex-1 rounded-2xl py-3.5 px-5" />
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
      {threadParent && (
        <ThreadPanel parent={threadParent} messages={messages} members={members} user={user}
          onReply={sendReply} onReact={react} onClose={() => setThreadParent(null)} />
      )}
    </div>
  );
}
