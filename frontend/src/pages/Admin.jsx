import { useEffect, useState } from "react";
import { Users, Layers, FolderKanban, FolderOpen, Plug, MessagesSquare, Shield } from "lucide-react";
import api from "@/lib/api";
import { PageShell, PageHeader, Loader } from "@/components/Stitch";

const CARDS = [
  { key: "total_users", label: "Users", icon: Users },
  { key: "total_workspaces", label: "Workspaces", icon: Layers },
  { key: "total_projects", label: "Projects", icon: FolderKanban },
  { key: "total_assets", label: "Assets", icon: FolderOpen },
  { key: "total_integrations", label: "Integrations", icon: Plug },
  { key: "total_messages", label: "Messages", icon: MessagesSquare },
];

export default function Admin() {
  const [stats, setStats] = useState(null);
  useEffect(() => { api.get("/admin/stats").then(({ data }) => setStats(data)).catch(() => setStats({})); }, []);
  if (!stats) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <PageHeader title="Admin Dashboard" subtitle="Platform-wide overview of Stitches usage and members." />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-5 mb-8">
        {CARDS.map(({ key, label, icon: Icon }, i) => (
          <div key={key} className="neu-raised neu-hover rounded-[1.5rem] p-6 animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
            <div className="neu-sm w-12 h-12 rounded-2xl flex items-center justify-center mb-4"><Icon className="w-6 h-6 text-primary-stitch" /></div>
            <p className="font-head font-black text-4xl" style={{ color: "var(--text)" }}>{stats[key] ?? 0}</p>
            <p className="text-sm text-muted-stitch mt-1">{label}</p>
          </div>
        ))}
      </div>

      <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up">
        <h2 className="font-head font-bold text-2xl mb-5" style={{ color: "var(--text)" }}>Recent Members</h2>
        <div className="space-y-3">
          {(stats.recent_users || []).map((u) => (
            <div key={u.user_id} className="neu-pressed rounded-2xl p-4 flex items-center gap-4">
              <div className="neu-sm w-11 h-11 rounded-full flex items-center justify-center overflow-hidden shrink-0">
                {u.avatar ? <img src={u.avatar} alt="" className="w-full h-full object-cover" /> :
                  <span className="font-head font-bold text-primary-stitch">{(u.name || "U")[0].toUpperCase()}</span>}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{u.name}</p>
                <p className="text-sm text-muted-stitch truncate">{u.email}</p>
              </div>
              <span className={`text-xs px-3 py-1.5 rounded-full font-semibold flex items-center gap-1 ${u.role === "admin" ? "neu-primary" : "neu-sm text-muted-stitch"}`}>
                {u.role === "admin" && <Shield className="w-3 h-3" />}{u.role}
              </span>
            </div>
          ))}
        </div>
      </div>
    </PageShell>
  );
}
