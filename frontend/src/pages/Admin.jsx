import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users, Layers, FolderKanban, FolderOpen, Plug, MessagesSquare, Shield,
  ToggleRight, Search, Activity, Grid3x3, LayoutDashboard, KeyRound, LogIn, BadgeCheck, Bell,
} from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageShell, PageHeader, Loader } from "@/components/Stitch";

const CARDS = [
  { key: "total_users", label: "Users", icon: Users },
  { key: "total_workspaces", label: "Workspaces", icon: Layers },
  { key: "total_projects", label: "Projects", icon: FolderKanban },
  { key: "total_assets", label: "Assets", icon: FolderOpen },
  { key: "total_integrations", label: "Integrations", icon: Plug },
  { key: "total_messages", label: "Messages", icon: MessagesSquare },
];

const TABS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "users", label: "Users", icon: Users },
  { id: "features", label: "Features", icon: ToggleRight },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "seo", label: "SEO", icon: Search },
  { id: "monitoring", label: "Monitoring", icon: Activity },
  { id: "heatmap", label: "Heat Map", icon: Grid3x3 },
];

export default function Admin() {
  const [tab, setTab] = useState("overview");
  return (
    <PageShell>
      <PageHeader title="Admin Dashboard" subtitle="Full control over Stitches — members, features, SEO, monitoring and activity heat maps." />
      <div className="neu-pressed rounded-full p-1.5 flex gap-1 mb-8 overflow-x-auto animate-fade-up">
        {TABS.map((t) => (
          <button key={t.id} data-testid={`admin-tab-${t.id}`} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 rounded-full py-2.5 px-4 text-sm font-semibold whitespace-nowrap transition-all ${tab === t.id ? "neu-primary" : "text-muted-stitch"}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>
      {tab === "overview" && <Overview />}
      {tab === "users" && <UsersTab />}
      {tab === "features" && <FeaturesTab />}
      {tab === "notifications" && <NotifGlobalTab />}
      {tab === "seo" && <SeoTab />}
      {tab === "monitoring" && <MonitoringTab />}
      {tab === "heatmap" && <HeatmapTab />}
    </PageShell>
  );
}

function Overview() {
  const [stats, setStats] = useState(null);
  useEffect(() => { api.get("/admin/stats").then(({ data }) => setStats(data)).catch(() => setStats({})); }, []);
  if (!stats) return <Loader />;
  return (
    <>
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
              <Avatar u={u} />
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{u.name}</p>
                <p className="text-sm text-muted-stitch truncate">{u.email}</p>
              </div>
              <RolePill role={u.role} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function UsersTab() {
  const [users, setUsers] = useState(null);
  const navigate = useNavigate();
  const { startImpersonation } = useAuth();
  const load = () => api.get("/admin/users").then(({ data }) => setUsers(data));
  useEffect(() => { load(); }, []);

  const toggleActive = async (u) => {
    await api.put(`/admin/users/${u.user_id}`, { is_active: u.is_active === false });
    toast.success(u.is_active === false ? "Account enabled" : "Account disabled"); load();
  };
  const toggleRole = async (u) => {
    await api.put(`/admin/users/${u.user_id}`, { role: u.role === "admin" ? "user" : "admin" });
    toast.success("Role updated"); load();
  };
  const resetPw = async (u) => {
    const pw = window.prompt(`Set a new password for ${u.email}:`);
    if (!pw) return;
    await api.post(`/admin/users/${u.user_id}/set-password`, { password: pw });
    toast.success("Password updated — share it securely with the user");
  };
  const impersonate = async (u) => {
    const { data } = await api.post(`/admin/users/${u.user_id}/impersonate`);
    startImpersonation(data.token, data.user);
    toast.success(`Now viewing as ${u.name}`);
    navigate("/dashboard");
  };

  if (!users) return <Loader />;
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up space-y-3">
      {users.map((u) => (
        <div key={u.user_id} className="neu-pressed rounded-2xl p-4 flex flex-wrap items-center gap-4" data-testid="admin-user-row">
          <Avatar u={u} />
          <div className="flex-1 min-w-0">
            <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{u.name}</p>
            <p className="text-sm text-muted-stitch truncate">{u.email}</p>
          </div>
          {u.is_active === false && <span className="text-xs px-3 py-1 rounded-full neu-sm text-red-500 font-semibold">Disabled</span>}
          <RolePill role={u.role} />
          <div className="flex gap-2">
            <ActionBtn onClick={() => toggleRole(u)} icon={BadgeCheck} title="Toggle admin" testid="btn-role" />
            <ActionBtn onClick={() => toggleActive(u)} icon={ToggleRight} title="Enable/disable" testid="btn-active" />
            <ActionBtn onClick={() => resetPw(u)} icon={KeyRound} title="Reset password" testid="btn-reset" />
            <ActionBtn onClick={() => impersonate(u)} icon={LogIn} title="Login as user" testid="btn-impersonate" primary />
          </div>
        </div>
      ))}
    </div>
  );
}

function FeaturesTab() {
  const [flags, setFlags] = useState(null);
  useEffect(() => { api.get("/admin/features").then(({ data }) => setFlags(data)); }, []);
  const toggle = async (key) => {
    const next = { ...flags, [key]: !flags[key] };
    setFlags(next);
    await api.put("/admin/features", { flags: { [key]: next[key] } });
    toast.success(`${LABELS[key] || key} ${next[key] ? "enabled" : "disabled"} for all users`);
  };
  if (!flags) return <Loader />;
  const LABELS = { chat: "Messaging", projects: "Projects", assets: "Assets", integrations: "Integrations", ai_assistant: "AI Assistant", friends: "People / Connections" };
  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up">
      <p className="text-muted-stitch mb-6">Turn features on or off across the entire platform. Disabled features are hidden from users and their APIs are blocked.</p>
      <div className="grid sm:grid-cols-2 gap-4">
        {Object.keys(LABELS).map((key) => (
          <div key={key} className="neu-pressed rounded-2xl p-5 flex items-center justify-between">
            <span className="font-semibold" style={{ color: "var(--text)" }}>{LABELS[key]}</span>
            <button data-testid={`feature-toggle-${key}`} onClick={() => toggle(key)}
              className={`w-14 h-8 rounded-full flex items-center px-1 transition-all ${flags[key] ? "justify-end" : "justify-start"}`}
              style={{ background: flags[key] ? "var(--primary)" : "var(--neu-dark)" }}>
              <span className="w-6 h-6 rounded-full bg-white shadow" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function NotifGlobalTab() {
  const [settings, setSettings] = useState(null);
  useEffect(() => { api.get("/admin/notifications-global").then(({ data }) => setSettings(data)); }, []);
  const toggle = async (key) => {
    const next = { ...settings, [key]: !settings[key] };
    setSettings(next);
    await api.put("/admin/notifications-global", { settings: { [key]: next[key] } });
    toast.success(`${LABELS[key]} ${next[key] ? "enabled" : "disabled"} platform-wide`);
  };
  if (!settings) return <Loader />;
  const LABELS = { master: "All notifications", workspace: "Workspace invites", project: "Project invites", friend: "New connections" };
  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up">
      <p className="text-muted-stitch mb-6">Control which notification types are delivered across the entire platform. When a type is off here, no user receives it (their personal preference is also respected).</p>
      <div className="grid sm:grid-cols-2 gap-4">
        {Object.keys(LABELS).map((key) => (
          <div key={key} className={`neu-pressed rounded-2xl p-5 flex items-center justify-between ${key !== "master" && !settings.master ? "opacity-50" : ""}`}>
            <span className="font-semibold" style={{ color: "var(--text)" }}>{LABELS[key]}</span>
            <button data-testid={`notif-global-${key}`} disabled={key !== "master" && !settings.master} onClick={() => toggle(key)}
              className={`w-14 h-8 rounded-full flex items-center px-1 transition-all ${settings[key] ? "justify-end" : "justify-start"}`}
              style={{ background: settings[key] ? "var(--primary)" : "var(--neu-dark)" }}>
              <span className="w-6 h-6 rounded-full bg-white shadow" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function SeoTab() {
  const [seo, setSeo] = useState(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { api.get("/seo").then(({ data }) => setSeo(data)); }, []);
  const save = async () => {
    setSaving(true);
    try { await api.put("/admin/seo", seo); toast.success("SEO settings saved"); document.title = seo.title; }
    catch (e) { toast.error("Failed"); } finally { setSaving(false); }
  };
  if (!seo) return <Loader />;
  const set = (k) => (e) => setSeo({ ...seo, [k]: e.target.value });
  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up space-y-5 max-w-2xl">
      <SeoField label="Site title" value={seo.title} onChange={set("title")} testid="seo-title" />
      <div>
        <label className="text-sm font-semibold text-muted-stitch">Meta description</label>
        <textarea data-testid="seo-description" value={seo.description || ""} onChange={set("description")} rows={3} className="neu-input w-full rounded-2xl py-3 px-5 mt-2 resize-none" />
      </div>
      <SeoField label="Keywords (comma separated)" value={seo.keywords} onChange={set("keywords")} testid="seo-keywords" />
      <SeoField label="Open Graph image URL" value={seo.og_image} onChange={set("og_image")} testid="seo-og" />
      <button data-testid="seo-save-btn" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold">{saving ? "Saving..." : "Save SEO"}</button>
    </div>
  );
}

function MonitoringTab() {
  const [data, setData] = useState(null);
  const [users, setUsers] = useState([]);
  const [selUser, setSelUser] = useState("");
  const [userLogs, setUserLogs] = useState(null);
  useEffect(() => {
    api.get("/admin/monitoring").then(({ data }) => setData(data));
    api.get("/admin/users").then(({ data }) => setUsers(data));
  }, []);

  const exportCsv = async () => {
    try {
      const res = await api.get("/admin/activity/export", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = "stitches_activity.csv"; a.click();
      URL.revokeObjectURL(url);
      toast.success("Activity log exported");
    } catch (e) { toast.error("Export failed"); }
  };

  const loadUser = async (uid) => {
    setSelUser(uid);
    setUserLogs(null);
    if (!uid) return;
    const { data } = await api.get(`/admin/users/${uid}/activity`);
    setUserLogs(data);
  };

  if (!data) return <Loader />;
  const maxDaily = Math.max(1, ...data.daily.map((d) => d.count));
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>System Monitoring</h3>
        <button data-testid="export-activity-btn" onClick={exportCsv} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2">
          <Search className="w-4 h-4" /> Export CSV
        </button>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <Metric label="Total Events" value={data.total_events} />
        <Metric label="Active Today" value={data.active_today} />
        <Metric label="Event Types" value={Object.keys(data.by_action).length} />
        <Metric label="Actions Logged" value={Object.values(data.by_action).reduce((a, b) => a + b, 0)} />
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up">
          <h3 className="font-head font-bold text-xl mb-5" style={{ color: "var(--text)" }}>Activity (last 7 days)</h3>
          <div className="flex items-end gap-3 h-40">
            {data.daily.length === 0 && <p className="text-muted-stitch">No activity yet.</p>}
            {data.daily.map((d) => (
              <div key={d.date} className="flex-1 flex flex-col items-center gap-2">
                <div className="neu-sm w-full rounded-t-xl" style={{ height: `${(d.count / maxDaily) * 100}%`, background: "var(--primary)", minHeight: 6 }} />
                <span className="text-[10px] text-muted-stitch">{d.date.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up">
          <h3 className="font-head font-bold text-xl mb-5" style={{ color: "var(--text)" }}>Live Activity Feed</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {data.feed.map((f, i) => (
              <div key={i} className="neu-pressed rounded-xl p-3 flex items-center gap-3">
                <span className="neu-sm text-xs px-2 py-1 rounded-md text-primary-stitch font-mono-stitch">{f.action}</span>
                <span className="text-sm truncate flex-1" style={{ color: "var(--text)" }}>{f.user_name}</span>
                <span className="text-xs text-muted-stitch">{new Date(f.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up">
        <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Per-user Activity</h3>
          <select data-testid="drilldown-user-select" value={selUser} onChange={(e) => loadUser(e.target.value)}
            className="neu-input rounded-2xl py-2.5 px-4 font-medium cursor-pointer" style={{ color: "var(--text)" }}>
            <option value="">Select a user…</option>
            {users.map((u) => <option key={u.user_id} value={u.user_id}>{u.name} ({u.email})</option>)}
          </select>
        </div>
        {!selUser && <p className="text-muted-stitch text-sm">Choose a member to trace exactly what they did and when.</p>}
        {selUser && userLogs === null && <Loader />}
        {userLogs && userLogs.length === 0 && <p className="text-muted-stitch text-sm">No recorded activity for this user.</p>}
        {userLogs && userLogs.length > 0 && (
          <div className="space-y-2 max-h-80 overflow-y-auto" data-testid="drilldown-logs">
            {userLogs.map((l, i) => (
              <div key={i} className="neu-pressed rounded-xl p-3 flex items-center gap-3">
                <span className="neu-sm text-xs px-2 py-1 rounded-md text-primary-stitch font-mono-stitch">{l.action}</span>
                <span className="text-xs text-muted-stitch flex-1 truncate">{JSON.stringify(l.meta || {})}</span>
                <span className="text-xs text-muted-stitch">{new Date(l.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function HeatmapTab() {
  const [grid, setGrid] = useState(null);
  useEffect(() => { api.get("/admin/heatmap").then(({ data }) => setGrid(data.grid)); }, []);
  if (!grid) return <Loader />;
  const max = Math.max(1, ...grid.flat());
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up overflow-x-auto">
      <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>Activity Heat Map</h3>
      <p className="text-sm text-muted-stitch mb-6">User activity intensity by day of week and hour (UTC).</p>
      <div className="inline-block min-w-full">
        {grid.map((row, d) => (
          <div key={d} className="flex items-center gap-1 mb-1">
            <span className="text-xs text-muted-stitch w-9 shrink-0">{days[d]}</span>
            {row.map((count, h) => {
              const intensity = count / max;
              return (
                <div key={h} title={`${days[d]} ${h}:00 — ${count} events`}
                  className="w-5 h-5 rounded-[4px] shrink-0"
                  style={{ background: count === 0 ? "var(--neu-dark)" : `rgba(220,38,38,${0.25 + intensity * 0.75})` }} />
              );
            })}
          </div>
        ))}
        <div className="flex gap-1 mt-1 ml-10">
          {Array.from({ length: 24 }).map((_, h) => (
            <span key={h} className="w-5 text-[9px] text-muted-stitch text-center shrink-0">{h % 3 === 0 ? h : ""}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function Avatar({ u }) {
  return (
    <div className="neu-sm w-11 h-11 rounded-full flex items-center justify-center overflow-hidden shrink-0">
      {u.avatar ? <img src={u.avatar} alt="" className="w-full h-full object-cover" /> :
        <span className="font-head font-bold text-primary-stitch">{(u.name || "U")[0].toUpperCase()}</span>}
    </div>
  );
}

function RolePill({ role }) {
  return (
    <span className={`text-xs px-3 py-1.5 rounded-full font-semibold flex items-center gap-1 ${role === "admin" ? "neu-primary" : "neu-sm text-muted-stitch"}`}>
      {role === "admin" && <Shield className="w-3 h-3" />}{role}
    </span>
  );
}

function ActionBtn({ onClick, icon: Icon, title, testid, primary }) {
  return (
    <button data-testid={testid} onClick={onClick} title={title}
      className={`w-10 h-10 rounded-xl flex items-center justify-center ${primary ? "neu-primary" : "neu-btn text-primary-stitch"}`}>
      <Icon className="w-4 h-4" />
    </button>
  );
}

function Metric({ label, value }) {
  return (
    <div className="neu-raised rounded-[1.5rem] p-6 animate-fade-up">
      <p className="font-head font-black text-4xl" style={{ color: "var(--text)" }}>{value}</p>
      <p className="text-sm text-muted-stitch mt-1">{label}</p>
    </div>
  );
}

function SeoField({ label, value, onChange, testid }) {
  return (
    <div>
      <label className="text-sm font-semibold text-muted-stitch">{label}</label>
      <input data-testid={testid} value={value || ""} onChange={onChange} className="neu-input w-full rounded-2xl py-3 px-5 mt-2" />
    </div>
  );
}
