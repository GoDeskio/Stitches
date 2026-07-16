import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LiveKitRoom, VideoConference, RoomAudioRenderer } from "@livekit/components-react";
import "@livekit/components-styles";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

export default function SfuCall({ roomId, serverUrl, audioOnly }) {
  const navigate = useNavigate();
  const [token, setToken] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.post("/rtc/sfu-token", { room_id: roomId });
        if (alive) setToken(data.token);
      } catch (e) { if (alive) setFailed(true); }
    })();
    return () => { alive = false; };
  }, [roomId]);

  if (failed) {
    return (
      <div className="stitch-wallpaper min-h-screen flex items-center justify-center">
        <div className="neu-raised rounded-3xl p-8 text-center">
          <p className="font-head font-bold text-xl mb-2" style={{ color: "var(--text)" }}>Couldn't join the SFU room</p>
          <p className="text-sm text-muted-stitch">The LiveKit server may be unreachable. Ask an admin to check the SFU settings.</p>
        </div>
      </div>
    );
  }
  if (!token) {
    return (
      <div className="stitch-wallpaper min-h-screen flex items-center justify-center gap-3" style={{ color: "var(--text)" }}>
        <Loader2 className="w-6 h-6 animate-spin text-primary-stitch" /> Connecting to meeting…
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="sfu-call-room" style={{ background: "#0e0e10" }}>
      <LiveKitRoom
        video={!audioOnly}
        audio={true}
        token={token}
        serverUrl={serverUrl}
        data-lk-theme="default"
        style={{ height: "100vh" }}
        onDisconnected={() => { toast.info("You left the meeting"); if (window.opener) window.close(); else navigate("/meetings"); }}
      >
        <VideoConference />
        <RoomAudioRenderer />
      </LiveKitRoom>
    </div>
  );
}
