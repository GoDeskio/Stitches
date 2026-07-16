import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Video, Plus, LogIn, Copy, ShieldCheck, MonitorUp, Mic } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, PageHeader } from "@/components/Stitch";

export default function Meetings() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [creating, setCreating] = useState(false);

  const openRoom = (roomId, newWindow) => {
    const url = `/call/${roomId}`;
    if (newWindow) {
      const w = window.open(url, "_blank", "width=1200,height=820");
      if (!w) navigate(url);
    } else navigate(url);
  };

  const start = async () => {
    setCreating(true);
    try {
      const { data } = await api.post("/meetings", {});
      toast.success("Meeting started");
      openRoom(data.room_id, true);
    } catch (e) { toast.error("Could not start meeting"); } finally { setCreating(false); }
  };

  const join = () => {
    const c = code.trim().replace(/^.*\/call\//, "");
    if (!c) { toast.error("Enter a meeting code or link"); return; }
    openRoom(c, false);
  };

  return (
    <PageShell>
      <PageHeader title="Meetings" subtitle="Start an instant audio & video call or join one with a code. Screen sharing included." />

      <div className="grid lg:grid-cols-2 gap-6 mb-8">
        <div className="neu-raised rounded-[1.75rem] p-8 animate-fade-up flex flex-col" data-testid="start-meeting-card">
          <div className="neu-sm w-14 h-14 rounded-3xl flex items-center justify-center mb-5"><Video className="w-7 h-7 text-primary-stitch" /></div>
          <h3 className="font-head font-bold text-2xl mb-2" style={{ color: "var(--text)" }}>Start an instant meeting</h3>
          <p className="text-muted-stitch mb-6 flex-1">Opens a private room in a new window with camera, microphone and screen sharing. Invite anyone with the link.</p>
          <button data-testid="start-meeting-btn" onClick={start} disabled={creating}
            className="neu-primary rounded-2xl py-3.5 font-semibold flex items-center justify-center gap-2">
            <Plus className="w-5 h-5" /> {creating ? "Starting…" : "New meeting"}
          </button>
        </div>

        <div className="neu-raised rounded-[1.75rem] p-8 animate-fade-up flex flex-col" data-testid="join-meeting-card">
          <div className="neu-sm w-14 h-14 rounded-3xl flex items-center justify-center mb-5"><LogIn className="w-7 h-7 text-primary-stitch" /></div>
          <h3 className="font-head font-bold text-2xl mb-2" style={{ color: "var(--text)" }}>Join a meeting</h3>
          <p className="text-muted-stitch mb-6">Paste a meeting code or invite link to join.</p>
          <input data-testid="join-code-input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="room_xxxxx or invite link"
            className="neu-input w-full rounded-2xl py-3.5 px-5 mb-4 font-mono-stitch" onKeyDown={(e) => e.key === "Enter" && join()} />
          <button data-testid="join-meeting-btn" onClick={join} className="neu-btn rounded-2xl py-3.5 font-semibold text-primary-stitch flex items-center justify-center gap-2">
            <LogIn className="w-5 h-5" /> Join
          </button>
        </div>
      </div>

      <div className="grid sm:grid-cols-3 gap-6">
        {[
          { icon: ShieldCheck, t: "Permission-aware", b: "Your browser asks for camera & mic access on join; you can join audio-only or watch-only if you decline." },
          { icon: MonitorUp, t: "Screen sharing", b: "Share your whole screen or a window to anyone in the room with one tap." },
          { icon: Mic, t: "Full controls", b: "Mute, stop video, share screen and end the call — all from the in-call toolbar." },
        ].map((f) => (
          <div key={f.t} className="neu-raised rounded-[1.5rem] p-6 animate-fade-up">
            <div className="neu-sm w-12 h-12 rounded-2xl flex items-center justify-center mb-4"><f.icon className="w-6 h-6 text-primary-stitch" /></div>
            <h4 className="font-head font-bold text-lg mb-2" style={{ color: "var(--text)" }}>{f.t}</h4>
            <p className="text-sm text-muted-stitch">{f.b}</p>
          </div>
        ))}
      </div>
    </PageShell>
  );
}
