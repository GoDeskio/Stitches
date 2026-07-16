import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Video, Plus, LogIn, CalendarPlus, CalendarClock, Users, X, Search, Check } from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageShell, PageHeader } from "@/components/Stitch";

export default function Meetings() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [code, setCode] = useState("");
  const [creating, setCreating] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [upcoming, setUpcoming] = useState([]);

  const loadUpcoming = () => api.get("/meetings/upcoming").then(({ data }) => setUpcoming(data)).catch(() => {});
  useEffect(() => { loadUpcoming(); }, []);

  const openRoom = (roomId, newWindow) => {
    const url = `/call/${roomId}`;
    if (newWindow) { const w = window.open(url, "_blank", "width=1200,height=820"); if (!w) navigate(url); }
    else navigate(url);
  };

  const startInstant = async () => {
    setCreating(true);
    try { const { data } = await api.post("/meetings", {}); toast.success("Meeting started"); openRoom(data.room_id, true); }
    catch (e) { toast.error("Could not start meeting"); } finally { setCreating(false); }
  };

  const join = () => {
    const c = code.trim().replace(/^.*\/call\//, "");
    if (!c) { toast.error("Enter a meeting code or link"); return; }
    openRoom(c, false);
  };

  const addToCalendar = (roomId) => window.open(`${API}/meetings/${roomId}/ics`, "_blank");

  return (
    <PageShell>
      <PageHeader title="Meetings" subtitle="Start an instant call, invite people, or schedule a meeting with email invites & calendar links." />

      <div className="grid lg:grid-cols-3 gap-6 mb-8">
        <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up flex flex-col" data-testid="start-meeting-card">
          <div className="neu-sm w-14 h-14 rounded-3xl flex items-center justify-center mb-4"><Video className="w-7 h-7 text-primary-stitch" /></div>
          <h3 className="font-head font-bold text-xl mb-2" style={{ color: "var(--text)" }}>Instant meeting</h3>
          <p className="text-muted-stitch mb-5 flex-1 text-sm">Open a private room right now with camera, mic and screen sharing.</p>
          <button data-testid="start-meeting-btn" onClick={startInstant} disabled={creating} className="neu-primary rounded-2xl py-3 font-semibold flex items-center justify-center gap-2">
            <Plus className="w-5 h-5" /> {creating ? "Starting…" : "New meeting"}
          </button>
        </div>

        <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up flex flex-col" data-testid="schedule-meeting-card">
          <div className="neu-sm w-14 h-14 rounded-3xl flex items-center justify-center mb-4"><CalendarPlus className="w-7 h-7 text-primary-stitch" /></div>
          <h3 className="font-head font-bold text-xl mb-2" style={{ color: "var(--text)" }}>Invite & schedule</h3>
          <p className="text-muted-stitch mb-5 flex-1 text-sm">Add users & friends, pick a time. They get an in-app alert + an email with a calendar invite.</p>
          <button data-testid="open-schedule-btn" onClick={() => setShowModal(true)} className="neu-btn rounded-2xl py-3 font-semibold text-primary-stitch flex items-center justify-center gap-2">
            <Users className="w-5 h-5" /> Invite people
          </button>
        </div>

        <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up flex flex-col" data-testid="join-meeting-card">
          <div className="neu-sm w-14 h-14 rounded-3xl flex items-center justify-center mb-4"><LogIn className="w-7 h-7 text-primary-stitch" /></div>
          <h3 className="font-head font-bold text-xl mb-2" style={{ color: "var(--text)" }}>Join a meeting</h3>
          <input data-testid="join-code-input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="room code or link"
            className="neu-input w-full rounded-2xl py-3 px-4 mb-3 font-mono-stitch text-sm" onKeyDown={(e) => e.key === "Enter" && join()} />
          <button data-testid="join-meeting-btn" onClick={join} className="neu-btn rounded-2xl py-3 font-semibold text-primary-stitch flex items-center justify-center gap-2">
            <LogIn className="w-5 h-5" /> Join
          </button>
        </div>
      </div>

      <h2 className="font-head font-bold text-2xl mb-4 flex items-center gap-2" style={{ color: "var(--text)" }}>
        <CalendarClock className="w-6 h-6 text-primary-stitch" /> Upcoming meetings
      </h2>
      {upcoming.length === 0 ? (
        <p className="text-muted-stitch neu-pressed rounded-2xl p-6 text-sm" data-testid="no-upcoming">No scheduled meetings yet. Use "Invite people" to schedule one.</p>
      ) : (
        <div className="space-y-3" data-testid="upcoming-list">
          {upcoming.map((m) => (
            <div key={m.room_id + m.scheduled_at} data-testid="upcoming-row" className="neu-raised rounded-2xl p-4 flex items-center gap-4 flex-wrap">
              <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0"><Video className="w-5 h-5 text-primary-stitch" /></div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate flex items-center gap-2" style={{ color: "var(--text)" }}>
                  {m.name}
                  {m.recurrence && m.recurrence !== "none" && (
                    <span data-testid="recurrence-badge" className="text-[11px] font-bold px-2 py-0.5 rounded-full text-white capitalize" style={{ background: "var(--primary)" }}>{m.recurrence}</span>
                  )}
                </p>
                <p className="text-xs text-muted-stitch">{new Date(m.scheduled_at + "Z").toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })} · {(m.invitees || []).length + 1} invited</p>
              </div>
              <button data-testid="add-calendar-btn" onClick={() => addToCalendar(m.room_id)} className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold text-primary-stitch flex items-center gap-1.5">
                <CalendarPlus className="w-4 h-4" /> Add to calendar
              </button>
              <button onClick={() => openRoom(m.room_id, true)} className="neu-primary rounded-xl px-4 py-2 text-sm font-semibold">Join</button>
            </div>
          ))}
        </div>
      )}

      {showModal && <ScheduleModal me={user} onClose={() => setShowModal(false)} onDone={() => { setShowModal(false); loadUpcoming(); }} openRoom={openRoom} />}
    </PageShell>
  );
}

function ScheduleModal({ me, onClose, onDone, openRoom }) {
  const [name, setName] = useState("");
  const [when, setWhen] = useState("");
  const [recurrence, setRecurrence] = useState("none");
  const [people, setPeople] = useState([]);
  const [selected, setSelected] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/users?limit=200").then(({ data }) => setPeople(data.filter((u) => u.user_id !== me?.user_id))).catch(() => {}); }, [me]);

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const filtered = people.filter((u) => (u.name || u.email || "").toLowerCase().includes(q.toLowerCase()));

  const submit = async (schedule) => {
    if (selected.length === 0) { toast.error("Select at least one person to invite"); return; }
    if (schedule && !when) { toast.error("Pick a date & time"); return; }
    setBusy(true);
    try {
      const payload = { name: name || undefined, invitee_ids: selected };
      if (schedule) { payload.scheduled_at = new Date(when).toISOString(); payload.recurrence = recurrence; }
      const { data } = await api.post("/meetings", payload);
      toast.success(schedule ? "Meeting scheduled — invites sent" : "Meeting started — invites sent");
      onDone();
      if (!schedule) openRoom(data.room_id, true);
    } catch (e) { toast.error("Failed to create meeting"); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className="neu-raised rounded-[1.75rem] p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="schedule-modal">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Invite people to a meeting</h3>
          <button data-testid="close-schedule-btn" onClick={onClose} className="text-muted-stitch hover:text-primary-stitch"><X className="w-5 h-5" /></button>
        </div>
        <input data-testid="meeting-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Meeting name (optional)" className="neu-input w-full rounded-2xl py-3 px-4 mb-3 text-sm" />
        <label className="text-xs font-semibold text-muted-stitch">Date & time (leave empty to start now)</label>
        <input data-testid="meeting-time-input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} className="neu-input w-full rounded-2xl py-3 px-4 mb-3 mt-1 text-sm" />
        <label className="text-xs font-semibold text-muted-stitch">Repeat</label>
        <div className="neu-pressed rounded-full p-1.5 flex mt-1 mb-3">
          {[["none", "Once"], ["daily", "Daily"], ["weekly", "Weekly"]].map(([val, lbl]) => (
            <button key={val} data-testid={`recurrence-${val}`} onClick={() => setRecurrence(val)}
              className={`flex-1 rounded-full py-2 text-sm font-semibold ${recurrence === val ? "neu-primary" : "text-muted-stitch"}`}>{lbl}</button>
          ))}
        </div>
        <div className="neu-pressed rounded-2xl p-2 mb-2 flex items-center gap-2">
          <Search className="w-4 h-4 text-muted-stitch ml-2" />
          <input data-testid="invitee-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search users & friends…" className="bg-transparent flex-1 py-1.5 text-sm outline-none" style={{ color: "var(--text)" }} />
        </div>
        <div className="space-y-1.5 max-h-56 overflow-y-auto mb-4" data-testid="invitee-list">
          {filtered.map((u) => (
            <button key={u.user_id} data-testid="invitee-option" onClick={() => toggle(u.user_id)}
              className={`w-full rounded-xl p-2.5 flex items-center gap-3 text-left ${selected.includes(u.user_id) ? "neu-pressed" : "neu-hover"}`}>
              <div className="neu-sm w-8 h-8 rounded-full flex items-center justify-center shrink-0 font-head font-bold text-primary-stitch text-sm">{(u.name || u.email || "?")[0].toUpperCase()}</div>
              <div className="min-w-0 flex-1"><p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{u.name}</p><p className="text-xs text-muted-stitch truncate">{u.email}</p></div>
              {selected.includes(u.user_id) && <Check className="w-4 h-4 text-primary-stitch shrink-0" />}
            </button>
          ))}
          {filtered.length === 0 && <p className="text-sm text-muted-stitch text-center py-4">No people found.</p>}
        </div>
        <div className="flex gap-3">
          <button data-testid="start-invite-btn" onClick={() => submit(false)} disabled={busy} className="neu-btn flex-1 rounded-2xl py-3 font-semibold text-primary-stitch">Start now & invite</button>
          <button data-testid="schedule-invite-btn" onClick={() => submit(true)} disabled={busy} className="neu-primary flex-1 rounded-2xl py-3 font-semibold">{busy ? "…" : "Schedule"}</button>
        </div>
        <p className="text-xs text-muted-stitch mt-3">Selected {selected.length} · invitees get an in-app alert{" "}and an email (if the admin has configured email) with a calendar invite.</p>
      </div>
    </div>
  );
}
