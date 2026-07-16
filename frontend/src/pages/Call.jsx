import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Mic, MicOff, Video, VideoOff, MonitorUp, PhoneOff, Copy, Users } from "lucide-react";
import { toast } from "sonner";
import { API } from "@/lib/api";

const ICE = [{ urls: "stun:stun.l.google.com:19302" }, { urls: "stun:global.stun.twilio.com:3478" }];

export default function Call() {
  const { roomId } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("connecting"); // connecting | live | error
  const [remotes, setRemotes] = useState({}); // peerId -> {name, stream}
  const [micOn, setMicOn] = useState(true);
  const [camOn, setCamOn] = useState(true);
  const [sharing, setSharing] = useState(false);

  const localVideoRef = useRef(null);
  const localStreamRef = useRef(null);
  const cameraTrackRef = useRef(null);
  const wsRef = useRef(null);
  const pcsRef = useRef({}); // peerId -> RTCPeerConnection
  const peerNamesRef = useRef({}); // peerId -> name
  const myIdRef = useRef(null);

  const setRemoteStream = (peerId, name, stream) => {
    setRemotes((prev) => ({ ...prev, [peerId]: { name, stream } }));
  };
  const removeRemote = (peerId) => setRemotes((prev) => { const n = { ...prev }; delete n[peerId]; return n; });

  const sendSignal = (to, data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "signal", to, data }));
  };

  const createPeer = useCallback((peerId, name, initiator) => {
    if (pcsRef.current[peerId]) return pcsRef.current[peerId];
    const pc = new RTCPeerConnection({ iceServers: ICE });
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
      try {
        localStreamRef.current = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
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
        } else if (msg.type === "peer-left") {
          const pc = pcsRef.current[msg.peer_id];
          if (pc) { pc.close(); delete pcsRef.current[msg.peer_id]; }
          removeRemote(msg.peer_id);
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

      <div className="flex-1 p-6 pt-0 overflow-y-auto">
        <div className={`grid gap-4`} style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }} data-testid="video-grid">
          <VideoTile refEl={localVideoRef} label="You" muted local camOn={camOn} sharing={sharing} />
          {remoteList.map(([pid, r]) => (
            <RemoteTile key={pid} peerId={pid} name={r.name} stream={r.stream} />
          ))}
        </div>
        {remoteList.length === 0 && (
          <p className="text-center text-muted-stitch mt-8" data-testid="waiting-note">Waiting for others to join — share the invite link above.</p>
        )}
      </div>

      <div className="flex items-center justify-center gap-3 py-6">
        <ControlBtn testid="toggle-mic-btn" active={micOn} onClick={toggleMic} on={<Mic className="w-5 h-5" />} off={<MicOff className="w-5 h-5" />} />
        <ControlBtn testid="toggle-cam-btn" active={camOn} onClick={toggleCam} on={<Video className="w-5 h-5" />} off={<VideoOff className="w-5 h-5" />} />
        <button data-testid="share-screen-btn" onClick={sharing ? stopShare : shareScreen}
          className={`w-14 h-14 rounded-2xl flex items-center justify-center ${sharing ? "neu-primary" : "neu-btn text-primary-stitch"}`}>
          <MonitorUp className="w-5 h-5" />
        </button>
        <button data-testid="end-call-btn" onClick={leave}
          className="w-16 h-14 rounded-2xl flex items-center justify-center text-white" style={{ background: "#dc2626" }}>
          <PhoneOff className="w-5 h-5" />
        </button>
      </div>
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

function VideoTile({ refEl, label, muted, camOn }) {
  return (
    <div className="neu-raised rounded-3xl overflow-hidden relative aspect-video bg-black/40">
      <video ref={refEl} autoPlay playsInline muted={muted} className="w-full h-full object-cover" style={{ transform: "scaleX(-1)" }} />
      {!camOn && <div className="absolute inset-0 flex items-center justify-center text-muted-stitch"><VideoOff className="w-8 h-8" /></div>}
      <span className="absolute bottom-2 left-3 text-xs font-semibold text-white bg-black/50 rounded-full px-2 py-0.5">{label}</span>
    </div>
  );
}

function RemoteTile({ name, stream }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current && stream) ref.current.srcObject = stream; }, [stream]);
  return (
    <div className="neu-raised rounded-3xl overflow-hidden relative aspect-video bg-black/40" data-testid="remote-tile">
      <video ref={ref} autoPlay playsInline className="w-full h-full object-cover" />
      <span className="absolute bottom-2 left-3 text-xs font-semibold text-white bg-black/50 rounded-full px-2 py-0.5">{name}</span>
    </div>
  );
}
