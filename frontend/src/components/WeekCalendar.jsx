import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays } from "lucide-react";
import api from "@/lib/api";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function startOfWeek(d) {
  const x = new Date(d);
  const day = (x.getDay() + 6) % 7; // Monday = 0
  x.setHours(0, 0, 0, 0);
  x.setDate(x.getDate() - day);
  return x;
}

export default function WeekCalendar() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);

  useEffect(() => {
    api.get("/meetings/upcoming").then(({ data }) => setItems(data)).catch(() => setItems([]));
  }, []);

  const weekStart = startOfWeek(new Date());
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(weekStart.getDate() + i);
    return d;
  });

  const meetingsFor = (day) =>
    items
      .filter((m) => {
        const dt = new Date(m.scheduled_at + "Z");
        return dt.toDateString() === day.toDateString();
      })
      .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));

  const today = new Date().toDateString();

  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up mt-6" data-testid="week-calendar-widget">
      <div className="flex items-center justify-between mb-5 gap-3 flex-wrap">
        <h2 className="font-head font-bold text-2xl flex items-center gap-2" style={{ color: "var(--text)" }}>
          <CalendarDays className="w-6 h-6 text-primary-stitch" /> This week
        </h2>
        <button onClick={() => navigate("/meetings")} className="text-sm text-primary-stitch font-semibold">Open meetings</button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {days.map((day, i) => {
          const dayMeetings = meetingsFor(day);
          const isToday = day.toDateString() === today;
          return (
            <div key={i} data-testid="week-day-cell"
              className={`neu-pressed rounded-2xl p-3 min-h-[7rem] ${isToday ? "ring-2" : ""}`}
              style={isToday ? { boxShadow: "inset 0 0 0 2px var(--primary)" } : {}}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-muted-stitch">{DAY_LABELS[i]}</span>
                <span className={`text-sm font-head font-black ${isToday ? "text-primary-stitch" : ""}`} style={!isToday ? { color: "var(--text)" } : {}}>{day.getDate()}</span>
              </div>
              <div className="space-y-1.5">
                {dayMeetings.length === 0 ? (
                  <span className="text-[11px] text-muted-stitch">—</span>
                ) : (
                  dayMeetings.slice(0, 3).map((m) => (
                    <button key={m.room_id + m.scheduled_at} data-testid="week-meeting-chip"
                      onClick={() => navigate(`/call/${m.room_id}`)}
                      className="w-full neu-sm rounded-lg px-2 py-1 text-left">
                      <p className="text-[11px] font-semibold truncate text-primary-stitch">
                        {new Date(m.scheduled_at + "Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </p>
                      <p className="text-[11px] truncate" style={{ color: "var(--text)" }}>{m.name}</p>
                    </button>
                  ))
                )}
                {dayMeetings.length > 3 && <span className="text-[10px] text-muted-stitch">+{dayMeetings.length - 3} more</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
