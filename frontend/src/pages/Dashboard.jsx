import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FolderKanban, FolderOpen, Plug, MessagesSquare, Layers, ArrowUpRight, Sparkles, CheckSquare, Circle, Video } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageShell, PageHeader, Loader } from "@/components/Stitch";
import MeetingLaunchButtons from "@/components/MeetingLaunchButtons";
import QrLoginCard from "@/components/QrLoginCard";

const STATS = [
  { key: "workspaces", label: "Workspaces", icon: Layers },
  { key: "projects", label: "Projects", icon: FolderKanban },
  { key: "assets", label: "Assets", icon: FolderOpen },
  { key: "integrations", label: "Integrations", icon: Plug },
  { key: "messages", label: "Messages Sent", icon: MessagesSquare },
];

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [myTasks, setMyTasks] = useState([]);

  useEffect(() => {
    api.get("/dashboard/stats").then(({ data }) => setStats(data)).catch(() => setStats({}));
    api.get("/tasks/mine").then(({ data }) => setMyTasks(data)).catch(() => setMyTasks([]));
  }, []);

  if (!stats) return <PageShell><Loader /></PageShell>;

  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <PageShell>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-2" data-testid="dashboard-call-bar">
        <PageHeader
          title={`${greet}, ${(user?.name || "").split(" ")[0] || "there"}`}
          subtitle="Here's what's happening across your Stitches workspaces today."
        />
        <div className="pt-1"><MeetingLaunchButtons /></div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-5 mb-8">
        {STATS.map(({ key, label, icon: Icon }, i) => (
          <div key={key} className="neu-raised neu-hover rounded-[1.5rem] p-6 animate-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
            <div className="neu-sm w-12 h-12 rounded-2xl flex items-center justify-center mb-4">
              <Icon className="w-6 h-6 text-primary-stitch" />
            </div>
            <p className="font-head font-black text-4xl" style={{ color: "var(--text)" }}>{stats[key] ?? 0}</p>
            <p className="text-sm text-muted-stitch mt-1">{label}</p>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 neu-raised rounded-[1.75rem] p-7 animate-fade-up">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Recent Projects</h2>
            <button onClick={() => navigate("/projects")} className="text-sm text-primary-stitch font-semibold flex items-center gap-1">
              View all <ArrowUpRight className="w-4 h-4" />
            </button>
          </div>
          {(stats.recent_projects?.length || 0) === 0 ? (
            <p className="text-muted-stitch py-8 text-center">No projects yet. Create one to get started.</p>
          ) : (
            <div className="space-y-3">
              {stats.recent_projects.map((p) => (
                <div key={p.project_id} className="neu-pressed rounded-2xl p-4 flex items-center justify-between">
                  <div>
                    <p className="font-semibold" style={{ color: "var(--text)" }}>{p.name}</p>
                    <p className="text-sm text-muted-stitch line-clamp-1">{p.description || "No description"}</p>
                  </div>
                  <span className="neu-sm text-xs px-3 py-1 rounded-full capitalize text-primary-stitch">{p.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up flex flex-col">
          <h2 className="font-head font-bold text-2xl mb-5" style={{ color: "var(--text)" }}>Quick Actions</h2>
          <div className="space-y-3 flex-1">
            <QuickAction icon={MessagesSquare} label="Open Messages" onClick={() => navigate("/messages")} />
            <QuickAction icon={Video} label="Start a Meeting" onClick={() => navigate("/meetings")} />
            <QuickAction icon={FolderKanban} label="New Project" onClick={() => navigate("/projects")} />
            <QuickAction icon={FolderOpen} label="Upload Asset" onClick={() => navigate("/assets")} />
            <QuickAction icon={Plug} label="Add Integration" onClick={() => navigate("/integrations")} />
          </div>
          <button onClick={() => navigate("/assistant")}
            className="neu-primary rounded-2xl py-3.5 mt-4 font-semibold flex items-center justify-center gap-2">
            <Sparkles className="w-5 h-5" /> Ask Stitch AI
          </button>
        </div>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up mt-6" data-testid="my-tasks-widget">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-head font-bold text-2xl flex items-center gap-2" style={{ color: "var(--text)" }}>
            <CheckSquare className="w-6 h-6 text-primary-stitch" /> My Tasks
          </h2>
          <span className="neu-sm text-xs px-3 py-1 rounded-full text-muted-stitch font-semibold">{myTasks.filter((t) => t.status !== "done").length} open</span>
        </div>
        {myTasks.length === 0 ? (
          <p className="text-muted-stitch py-6 text-center">No tasks yet. Open a project's board to add some.</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {myTasks.filter((t) => t.status !== "done")
              .sort((a, b) => (a.due_date || "9999").localeCompare(b.due_date || "9999"))
              .slice(0, 9).map((t) => (
              <button key={t.task_id} data-testid="my-task-row" onClick={() => navigate(`/projects/${t.project_id}/board`)}
                className="neu-pressed neu-hover rounded-2xl p-4 text-left flex items-start gap-3">
                <Circle className={`w-4 h-4 mt-0.5 shrink-0 ${t.status === "doing" ? "text-primary-stitch" : "text-muted-stitch"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{t.title}</p>
                  <p className="text-xs text-muted-stitch truncate">{t.project_name}{t.assignee_name ? ` · ${t.assignee_name}` : ""}</p>
                  {t.due_date && (
                    <span className={`text-[11px] font-semibold ${new Date(t.due_date) < new Date(new Date().toDateString()) ? "text-red-500" : "text-primary-stitch"}`}>
                      Due {new Date(t.due_date).toLocaleDateString([], { month: "short", day: "numeric" })}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="mt-6">
        <QrLoginCard />
      </div>
    </PageShell>
  );
}

function QuickAction({ icon: Icon, label, onClick }) {
  return (
    <button onClick={onClick} className="neu-btn w-full rounded-2xl py-3.5 px-4 flex items-center gap-3 font-medium" style={{ color: "var(--text)" }}>
      <Icon className="w-5 h-5 text-primary-stitch" /> {label}
    </button>
  );
}
