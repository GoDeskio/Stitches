import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Check, UserPlus, FolderKanban, Layers, Users, ShieldAlert, Video } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

const ICONS = { workspace: Layers, project: FolderKanban, friend: Users, security: ShieldAlert, meeting: Video };

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [filter, setFilter] = useState("all");
  const navigate = useNavigate();
  const lastIds = useRef(null);

  const load = async () => {
    try {
      const { data } = await api.get("/notifications");
      if (lastIds.current !== null) {
        const newOnes = data.notifications.filter((n) => !lastIds.current.has(n.notification_id) && !n.read);
        newOnes.forEach((n) => {
          if (n.type === "meeting" && n.link) {
            toast(n.title, { description: n.body, duration: 15000, action: { label: "Join", onClick: () => navigate(n.link) } });
          } else {
            toast(n.title, { description: n.body });
          }
        });
      }
      lastIds.current = new Set(data.notifications.map((n) => n.notification_id));
      setItems(data.notifications);
      setUnread(data.unread);
    } catch (e) {}
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const markAll = async () => { await api.post("/notifications/read-all"); load(); };
  const openItem = async (n) => {
    await api.post(`/notifications/${n.notification_id}/read`);
    setOpen(false);
    if (n.link) navigate(n.link);
    load();
  };

  return (
    <div className="relative">
      <button data-testid="notif-bell" onClick={() => setOpen((o) => !o)}
        className="neu-btn w-11 h-11 rounded-2xl flex items-center justify-center relative" style={{ color: "var(--text)" }}>
        <Bell className="w-5 h-5" />
        {unread > 0 && (
          <span data-testid="notif-badge" className="absolute -top-1 -right-1 min-w-[20px] h-5 px-1 rounded-full text-[11px] font-bold flex items-center justify-center text-white" style={{ background: "var(--primary)" }}>
            {unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="neu-raised absolute right-0 mt-3 w-80 rounded-3xl p-4 z-50 animate-fade-up" data-testid="notif-panel">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>Notifications</h4>
              {unread > 0 && <button onClick={markAll} className="text-xs text-primary-stitch font-semibold flex items-center gap-1"><Check className="w-3 h-3" /> Mark all read</button>}
            </div>
            <div className="neu-pressed rounded-full p-1 flex mb-3">
              <button data-testid="notif-filter-all" onClick={() => setFilter("all")}
                className={`flex-1 rounded-full py-1.5 text-xs font-bold uppercase tracking-wider ${filter === "all" ? "neu-primary" : "text-muted-stitch"}`}>All</button>
              <button data-testid="notif-filter-security" onClick={() => setFilter("security")}
                className={`flex-1 rounded-full py-1.5 text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-1 ${filter === "security" ? "neu-primary" : "text-muted-stitch"}`}>
                <ShieldAlert className="w-3.5 h-3.5" /> Security
              </button>
            </div>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {(() => {
                const shown = filter === "security" ? items.filter((n) => n.type === "security") : items;
                if (shown.length === 0) return <p className="text-sm text-muted-stitch py-6 text-center">{filter === "security" ? "No security alerts." : "You're all caught up."}</p>;
                return shown.map((n) => {
                  const Icon = ICONS[n.type] || UserPlus;
                  const isSec = n.type === "security";
                  return (
                    <button key={n.notification_id} data-testid={isSec ? "notif-security-item" : "notif-item"} onClick={() => openItem(n)}
                      className={`w-full text-left rounded-2xl p-3 flex gap-3 ${n.read ? "neu-hover" : "neu-pressed"}`}
                      style={isSec ? { borderLeft: "3px solid #dc2626" } : {}}>
                      <div className="neu-sm w-9 h-9 rounded-xl flex items-center justify-center shrink-0">
                        <Icon className="w-4 h-4" style={{ color: isSec ? "#dc2626" : "var(--primary)" }} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{n.title}</p>
                        <p className="text-xs text-muted-stitch line-clamp-2">{n.body}</p>
                      </div>
                      {!n.read && <span className="w-2 h-2 rounded-full mt-1.5 shrink-0" style={{ background: isSec ? "#dc2626" : "var(--primary)" }} />}
                    </button>
                  );
                });
              })()}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
