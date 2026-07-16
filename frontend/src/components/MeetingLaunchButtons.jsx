import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Video, Phone } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

export default function MeetingLaunchButtons() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const launch = async (audio) => {
    setBusy(true);
    try {
      const { data } = await api.post("/meetings", {});
      const path = `/call/${data.room_id}${audio ? "?mode=audio" : ""}`;
      const w = window.open(path, "_blank", "width=1200,height=820");
      if (!w) navigate(path);
      toast.success(audio ? "Audio call started" : "Video meeting started");
    } catch (e) { toast.error("Could not start the call"); } finally { setBusy(false); }
  };
  return (
    <div className="flex items-center gap-3">
      <button data-testid="start-video-call-btn" onClick={() => launch(false)} disabled={busy} title="Start a video meeting"
        className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2">
        <Video className="w-5 h-5" /> <span className="hidden sm:inline">Video meeting</span>
      </button>
      <button data-testid="start-audio-call-btn" onClick={() => launch(true)} disabled={busy} title="Start an audio call"
        className="neu-btn rounded-2xl px-5 py-3 font-semibold text-primary-stitch flex items-center gap-2">
        <Phone className="w-5 h-5" /> <span className="hidden sm:inline">Audio call</span>
      </button>
    </div>
  );
}
