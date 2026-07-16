import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Mic, MicOff, Video, VideoOff, MonitorUp, PhoneOff, Copy, Users, Hand, MessageSquare, Send, X } from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";

const ICE = [{ urls: "stun:stun.l.google.com:19302" }, { urls: "stun:global.stun.twilio.com:3478" }];

export default function Call() {
  const { roomId } = useParams();
  const [sp] = useSearchParams();
  const audioOnly = sp.get("mode") === "audio";
  const navigate = useNavigate();
  const [status, setStatus] = useState("connecting"); // connecting | live | error
  const [remotes, setRemotes] = useState({}); // peerId -> {name, stream}
  const [micOn, setMicOn] = useState(true);
  const [camOn, setCamOn] = useState(!audioOnly);
  const [sharing, setSharing] = useState(false);
  const [panel, setPanel] = useState(null); // 'chat' | 'people' | null
  const [chatMsgs, setChatMsgs] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [unread, setUnread] = useState(0);
  const [selfHand, setSelfHand] = useState(false);
  const [hands, setHands] = useState({}); // peerId -> bool

  const iceRef = useRef(ICE);
  const panelRef = useRef(null);
  const localVideoRef = useRef(null);
  const localStreamRef = useRef(null);
  const cameraTrackRef = useRef(null);
  const wsRef = useRef(null);
  const pcsRef = useRef({}); // peerId -> RTCPeerConnection
  const peerNamesRef = useRef({}); // peerId -> name
  const myIdRef = useRef(null);

  useEffect(() => { panelRef.current = panel; if (panel === "chat") setUnread(0); }, [panel]);

  const setRemoteStream = (peerId, name, stream) => {
    setRemotes((prev) => ({ ...prev, [peerId]: { name, stream } }));
  };
  const removeRemote = (peerId) => setRemotes((prev) => { const n = { ...prev }; delete n[peerId]; return n; });

  const sendSignal = (to, data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "signal", to, data }));
  };

  const createPeer = useCallback((peerId, name, initiator) => {
    if (pcsRef.current[peerId]) return pcsRef.current[peerId];
    const pc = new RTCPeerConnection({ iceServers: iceRef.current });
    pcsRef.current[peerId] = pc;
    if (localStreamRef.current) localStreamRef.current.getTracks().forEach((t) => pc.addTrack(t, localStreamRef.current));
    pc.onicecandidate = (e) => { if (e.candidate) sendSignal(peerId, { candidate: e.candidate }); };
    pc.ontrack = (e) => setRemoteStream(peerId, name, e.streams[0]);
    pc.onconnectionstatechange = () => {
      if (["failed", "closed", "disconnected"].includes(pc.connectionState)) { /* keep tile until peer-left */ }
    };
    if (initiator) {
      pc.onnegotiationneeded = async () => {
        try {
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          sendSignal(peerId, { sdp: pc.localDescription });
        } catch (e) {}
      };
    }
    return pc;
  }, []);

  const handleSignal = useCallback(async (from, name, data) => {
    let pc = pcsRef.current[from];
    if (data.sdp) {
      if (!pc) pc = createPeer(from, name, false);
      await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
      if (data.sdp.type === "offer") {
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        sendSignal(from, { sdp: pc.localDescription });
      }
    } else if (data.candidate && pc) {
      try { await pc.addIceCandidate(new RTCIceCandidate(data.candidate)); } catch (e) {}
    }
  }, [createPeer]);

  useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem("stitches_token");

    (async () => {
      try { const { data } = await api.get("/rtc/config"); if (data?.iceServers?.length) iceRef.current = data.iceServers; } catch (e) {}
      try {
        localStreamRef.current = await navigator.mediaDevices.getUserMedia({ video: !audioOnly, audio: true });
      } catch (e) {
        try { localStreamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true }); setCamOn(false); toast.warning("Camera unavailable — joined with audio only."); }
        catch (e2) { toast.error("Microphone & camera blocked. You can watch/listen only."); localStreamRef.current = null; setMicOn(false); setCamOn(false); }
      }
      if (cancelled) return;
      cameraTrackRef.current = localStreamRef.current?.getVideoTracks()[0] || null;
      if (localVideoRef.current && localStreamRef.current) localVideoRef.current.srcObject = localStreamRef.current;

      const wsUrl = API.replace(/^http/, "ws") + `/ws/call/${roomId}?token=${token}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => setStatus("live");
      ws.onerror = () => setStatus("error");
      ws.onclose = () => { if (!cancelled) setStatus((s) => (s === "live" ? "live" : "error")); };
      ws.onmessage = async (evt) => {
        const msg = JSON.parse(evt.data);
        if (msg.type === "welcome") {
          myIdRef.current = msg.peer_id;
          msg.peers.forEach((p) => { peerNamesRef.current[p.peer_id] = p.name; createPeer(p.peer_id, p.name, true); });
        } else if (msg.type === "peer-joined") {
          peerNamesRef.current[msg.peer_id] = msg.name;
        } else if (msg.type === "signal") {
          await handleSignal(msg.from, peerNamesRef.current[msg.from] || "Guest", msg.data);
        } else if (msg.type === "chat") {
          setChatMsgs((p) => [...p, { name: msg.name || "Guest", text: msg.text, self: false }]);
          if (panelRef.current !== "chat") setUnread((u) => u + 1);
        } else if (msg.type === "hand") {
          setHands((p) => ({ ...p, [msg.from]: msg.raised }));
        } else if (msg.type === "peer-left") {
          const pc = pcsRef.current[msg.peer_id];
          if (pc) { pc.close(); delete pcsRef.current[msg.peer_id]; }
          removeRemote(msg.peer_id);
          setHands((p) => { const n = { ...p }; delete n[msg.peer_id]; return n; });
        } else if (msg.type === "ended") {
          toast.info("The meeting was ended by an admin.");
          cleanup(); navigate("/meetings");
        }
      };
    })();

    return () => { cancelled = true; cleanup(); };
    // eslint-disable-line
  }, [roomId]); // eslint-disable-line

  const cleanup = () => {
    try { wsRef.current?.send(JSON.stringify({ type: "leave" })); } catch (e) {}
    try { wsRef.current?.close(); } catch (e) {}
    Object.values(pcsRef.current).forEach((pc) => { try { pc.close(); } catch (e) {} });
    pcsRef.current = {};
    localStreamRef.current?.getTracks().forEach((t) => t.stop());
  };

  const toggleMic = () => {
    const track = localStreamRef.current?.getAudioTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    setMicOn(track.enabled);
  };
  const toggleCam = () => {
    const track = cameraTrackRef.current;
    if (!track) return;
    track.enabled = !track.enabled;
    setCamOn(track.enabled);
  };

  const replaceVideoTrack = (newTrack) => {
    Object.values(pcsRef.current).forEach((pc) => {
      const sender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
      if (sender) sender.replaceTrack(newTrack);
    });
  };

  const shareScreen = async () => {
    if (sharing) return;
    try {
      const ds = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const screenTrack = ds.getVideoTracks()[0];
      replaceVideoTrack(screenTrack);
      if (localVideoRef.current) localVideoRef.current.srcObject = ds;
      setSharing(true);
      screenTrack.onended = stopShare;
    } catch (e) { /* user cancelled */ }
  };
  const stopShare = () => {
    const cam = cameraTrackRef.current;
    if (cam) replaceVideoTrack(cam);
    if (localVideoRef.current && localStreamRef.current) localVideoRef.current.srcObject = localStreamRef.current;
    setSharing(false);
  };

  const leave = () => { cleanup(); if (window.opener) window.close(); else navigate("/meetings"); };

  const sendChat = () => {
    const text = chatInput.trim();
    if (!text) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "chat", text }));
    setChatMsgs((p) => [...p, { name: "You", text, self: true }]);
    setChatInput("");
  };
  const toggleHand = () => {
    const raised = !selfHand;
    setSelfHand(raised);
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "hand", raised }));
  };

  const copyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    toast.success("Invite link copied");
  };

  const remoteList = Object.entries(remotes);
  const total = remoteList.length + 1;
  const cols = total <= 1 ? 1 : total <= 4 ? 2 : 3;

  return (
    <div className="stitch-wallpaper min-h-screen flex flex-col" data-testid="call-room">
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="" className="w-9 h-9 object-contain" />
          <div>
            <p className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>Stitches Meeting</p>
            <p className="text-xs text-muted-stitch flex items-center gap-1.5"><Users className="w-3.5 h-3.5" /> {total} in call · {status === "live" ? "Connected" : status}</p>
          </div>
        </div>
        <button data-testid="copy-invite-btn" onClick={copyLink} className="neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold text-primary-stitch flex items-center gap-2">
          <Copy className="w-4 h-4" /> Copy invite
        </button>
      </div>

      <div className="flex-1 p-6 pt-0 overflow-y-auto transition-all" style={{ marginRight: panel ? "20rem" : 0 }}>
        <div className={`grid gap-4`} style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }} data-testid="video-grid">
          <VideoTile refEl={localVideoRef} label="You" muted local camOn={camOn} sharing={sharing} raised={selfHand} />
          {remoteList.map(([pid, r]) => (
            <RemoteTile key={pid} peerId={pid} name={r.name} stream={r.stream} raised={!!hands[pid]} />
          ))}
        </div>
        {remoteList.length === 0 && (
          <p className="text-center text-muted-stitch mt-8" data-testid="waiting-note">Waiting for others to join — share the invite link above.</p>
        )}
      </div>

      {panel && (
        <div data-testid="call-panel" className="fixed right-0 top-0 bottom-0 w-80 neu-raised z-40 flex flex-col p-4" style={{ borderRadius: 0 }}>
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>{panel === "chat" ? "In-call chat" : "Participants"}</h4>
            <button data-testid="close-panel-btn" onClick={() => setPanel(null)} className="text-muted-stitch hover:text-primary-stitch"><X className="w-5 h-5" /></button>
          </div>
          {panel === "people" ? (
            <div className="space-y-2 overflow-y-auto" data-testid="participants-list">
              <PersonRow name="You" raised={selfHand} />
              {remoteList.map(([pid, r]) => <PersonRow key={pid} name={r.name} raised={!!hands[pid]} />)}
            </div>
          ) : (
            <>
              <div className="flex-1 space-y-3 overflow-y-auto mb-3" data-testid="chat-messages">
                {chatMsgs.length === 0 && <p className="text-sm text-muted-stitch text-center py-6">No messages yet.</p>}
                {chatMsgs.map((m, i) => (
                  <div key={i} className={`text-sm ${m.self ? "text-right" : ""}`}>
                    <span className="text-xs font-semibold text-primary-stitch">{m.name}</span>
                    <div className={`neu-pressed rounded-2xl px-3 py-2 mt-1 inline-block max-w-[85%] text-left`} style={{ color: "var(--text)" }}>{m.text}</div>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <input data-testid="chat-input" value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendChat()}
                  placeholder="Message…" className="neu-input flex-1 rounded-2xl py-2.5 px-4 text-sm" />
                <button data-testid="chat-send-btn" onClick={sendChat} className="neu-primary rounded-2xl w-11 flex items-center justify-center"><Send className="w-4 h-4" /></button>
              </div>
            </>
          )}
        </div>
      )}

      <div className="flex items-center justify-center gap-3 py-6 flex-wrap">
        <ControlBtn testid="toggle-mic-btn" active={micOn} onClick={toggleMic} on={<Mic className="w-5 h-5" />} off={<MicOff className="w-5 h-5" />} />
        <ControlBtn testid="toggle-cam-btn" active={camOn} onClick={toggleCam} on={<Video className="w-5 h-5" />} off={<VideoOff className="w-5 h-5" />} />
        <button data-testid="share-screen-btn" onClick={sharing ? stopShare : shareScreen}
          className={`w-14 h-14 rounded-2xl flex items-center justify-center ${sharing ? "neu-primary" : "neu-btn text-primary-stitch"}`}>
          <MonitorUp className="w-5 h-5" />
        </button>
        <button data-testid="raise-hand-btn" onClick={toggleHand}
          className={`w-14 h-14 rounded-2xl flex items-center justify-center ${selfHand ? "neu-primary" : "neu-btn text-primary-stitch"}`}>
          <Hand className="w-5 h-5" />
        </button>
        <button data-testid="people-btn" onClick={() => setPanel((p) => (p === "people" ? null : "people"))}
          className={`w-14 h-14 rounded-2xl flex items-center justify-center relative ${panel === "people" ? "neu-primary" : "neu-btn text-primary-stitch"}`}>
          <Users className="w-5 h-5" />
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold flex items-center justify-center text-white" style={{ background: "var(--primary)" }}>{total}</span>
        </button>
        <button data-testid="chat-btn" onClick={() => setPanel((p) => (p === "chat" ? null : "chat"))}
          className={`w-14 h-14 rounded-2xl flex items-center justify-center relative ${panel === "chat" ? "neu-primary" : "neu-btn text-primary-stitch"}`}>
          <MessageSquare className="w-5 h-5" />
          {unread > 0 && <span data-testid="chat-unread" className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold flex items-center justify-center text-white" style={{ background: "#dc2626" }}>{unread}</span>}
        </button>
        <button data-testid="end-call-btn" onClick={leave}
          className="w-16 h-14 rounded-2xl flex items-center justify-center text-white" style={{ background: "#dc2626" }}>
          <PhoneOff className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

function PersonRow({ name, raised }) {
  return (
    <div className="neu-pressed rounded-2xl p-3 flex items-center gap-3" data-testid="participant-row">
      <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center shrink-0 font-head font-bold text-primary-stitch">{(name || "?").slice(0, 1).toUpperCase()}</div>
      <span className="text-sm font-semibold flex-1 truncate" style={{ color: "var(--text)" }}>{name}</span>
      {raised && <Hand className="w-4 h-4 text-primary-stitch" data-testid="participant-hand" />}
    </div>
  );
}

function ControlBtn({ testid, active, onClick, on, off }) {
  return (
    <button data-testid={testid} onClick={onClick}
      className={`w-14 h-14 rounded-2xl flex items-center justify-center ${active ? "neu-btn text-primary-stitch" : "neu-pressed text-muted-stitch"}`}>
      {active ? on : off}
    </button>
  );
}

function VideoTile({ refEl, label, muted, camOn, raised }) {
  return (
    <div className="neu-raised rounded-3xl overflow-hidden relative aspect-video bg-black/40">
      <video ref={refEl} autoPlay playsInline muted={muted} className="w-full h-full object-cover" style={{ transform: "scaleX(-1)" }} />
      {!camOn && <div className="absolute inset-0 flex items-center justify-center text-muted-stitch"><VideoOff className="w-8 h-8" /></div>}
      {raised && <span className="absolute top-2 right-2 neu-primary rounded-full w-8 h-8 flex items-center justify-center" data-testid="tile-hand"><Hand className="w-4 h-4 text-white" /></span>}
      <span className="absolute bottom-2 left-3 text-xs font-semibold text-white bg-black/50 rounded-full px-2 py-0.5">{label}</span>
    </div>
  );
}

function RemoteTile({ name, stream, raised }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current && stream) ref.current.srcObject = stream; }, [stream]);
  return (
    <div className="neu-raised rounded-3xl overflow-hidden relative aspect-video bg-black/40" data-testid="remote-tile">
      <video ref={ref} autoPlay playsInline className="w-full h-full object-cover" />
      {raised && <span className="absolute top-2 right-2 neu-primary rounded-full w-8 h-8 flex items-center justify-center"><Hand className="w-4 h-4 text-white" /></span>}
      <span className="absolute bottom-2 left-3 text-xs font-semibold text-white bg-black/50 rounded-full px-2 py-0.5">{name}</span>
    </div>
  );
}
