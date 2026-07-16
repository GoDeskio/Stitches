import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users, Layers, FolderKanban, FolderOpen, Plug, MessagesSquare, Shield,
  ToggleRight, Search, Activity, Grid3x3, LayoutDashboard, KeyRound, LogIn, BadgeCheck, Bell,
  Ban, UserCheck, Download, Video, Plus, PhoneOff, Users as UsersIcon, Workflow, Megaphone, LifeBuoy, Mail, Check, ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageShell, PageHeader, Loader } from "@/components/Stitch";
import { IntegrationsManager } from "@/pages/Integrations";
import MeetingLaunchButtons from "@/components/MeetingLaunchButtons";

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
  { id: "integrations", label: "Integrations", icon: Plug },
  { id: "automation", label: "Automation", icon: Workflow },
  { id: "sitenote", label: "Site Note", icon: Megaphone },
  { id: "support", label: "Support", icon: LifeBuoy },
  { id: "meetings", label: "Meetings", icon: Video },
];

function EmailHealthBadge() {
  const [health, setHealth] = useState(null);
  useEffect(() => {
    const load = () => api.get("/admin/email-health").then(({ data }) => setHealth(data)).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);
  if (!health) return null;
  const hasData = health.at != null;
  const ok = health.ok === true;
  const color = !hasData ? "#9ca3af" : ok ? "#16a34a" : "#ef4444";
  const label = !hasData ? "No emails sent yet" : ok ? "Email working" : "Email failing";
  const when = hasData ? new Date(health.at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  return (
    <div data-testid="email-health-badge" title={`${label}${when ? ` · last: ${when}` : ""}${health.detail ? `\n${health.detail}` : ""}`}
      className="neu-pressed rounded-full pl-2.5 pr-3.5 py-2 flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--text)" }}>
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
      {label}
    </div>
  );
}

export default function Admin() {
  const [tab, setTab] = useState("overview");
  const [openSupport, setOpenSupport] = useState(0);
  useEffect(() => {
    api.get("/admin/support-requests", { params: { status: "open", limit: 1 } })
      .then(({ data }) => setOpenSupport(data.open_count || 0)).catch(() => {});
  }, [tab]);
  return (
    <PageShell>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-2" data-testid="admin-call-bar">
        <PageHeader title="Admin Dashboard" subtitle="Full control over Stitches — members, features, SEO, monitoring and activity heat maps." />
        <div className="pt-1 flex items-center gap-3"><EmailHealthBadge /><MeetingLaunchButtons /></div>
      </div>
      <div className="neu-pressed rounded-full p-1.5 flex gap-1 mb-8 overflow-x-auto animate-fade-up">
        {TABS.map((t) => (
          <button key={t.id} data-testid={`admin-tab-${t.id}`} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 rounded-full py-2.5 px-4 text-sm font-semibold whitespace-nowrap transition-all ${tab === t.id ? "neu-primary" : "text-muted-stitch"}`}>
            <t.icon className="w-4 h-4" /> {t.label}
            {t.id === "support" && openSupport > 0 && (
              <span data-testid="support-tab-badge" className="ml-0.5 min-w-[1.25rem] h-5 px-1.5 rounded-full bg-red-500 text-white text-[11px] font-bold flex items-center justify-center">{openSupport > 99 ? "99+" : openSupport}</span>
            )}
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
      {tab === "integrations" && <IntegrationsTab />}
      {tab === "automation" && <AutomationTab />}
      {tab === "sitenote" && <SiteNoteTab />}
      {tab === "support" && <SupportTab />}
      {tab === "meetings" && <MeetingsTab />}
    </PageShell>
  );
}

function Overview() {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  useEffect(() => {
    api.get("/admin/stats").then(({ data }) => setStats(data)).catch(() => setStats({}));
    api.get("/admin/automation-health").then(({ data }) => setHealth(data)).catch(() => setHealth(null));
  }, []);
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
      {health && health.total > 0 && (
        <div className="neu-raised rounded-[1.75rem] p-6 mb-8 animate-fade-up" data-testid="automation-health-card">
          <div className="flex items-center gap-3 mb-5">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Workflow className="w-5 h-5 text-primary-stitch" /></div>
            <div>
              <h2 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Automation health</h2>
              <p className="text-sm text-muted-stitch">Integration workflow reliability across the platform.</p>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <HealthStat label="Success rate" value={`${health.success_rate}%`} color={health.success_rate >= 90 ? "#16a34a" : health.success_rate >= 70 ? "#d97706" : "#dc2626"} />
            <HealthStat label="Total runs" value={health.total} />
            <HealthStat label="Failed runs" value={health.fail_count} color={health.fail_count > 0 ? "#dc2626" : undefined} />
            <HealthStat label="Failing now" value={health.failing} color={health.failing > 0 ? "#dc2626" : "#16a34a"} testid="health-failing" />
          </div>
        </div>
      )}
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

function HealthStat({ label, value, color, testid }) {
  return (
    <div className="neu-pressed rounded-2xl p-4" data-testid={testid}>
      <p className="font-head font-black text-3xl" style={{ color: color || "var(--text)" }}>{value}</p>
      <p className="text-xs text-muted-stitch mt-1">{label}</p>
    </div>
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
    toast.success(u.is_active === false ? "Account reinstated" : "Account disabled"); load();
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
          <div className="flex gap-2 items-center flex-wrap">
            <button
              data-testid="btn-active"
              onClick={() => toggleActive(u)}
              className={`text-sm font-semibold rounded-xl px-4 py-2 flex items-center gap-2 transition-transform hover:scale-[1.03] ${u.is_active === false ? "neu-primary" : "neu-sm text-red-500"}`}
              title={u.is_active === false ? "Reinstate this account" : "Disable this account"}
            >
              {u.is_active === false ? <><UserCheck className="w-4 h-4" /> Reinstate Account</> : <><Ban className="w-4 h-4" /> Disable Account</>}
            </button>
            <ActionBtn onClick={() => toggleRole(u)} icon={BadgeCheck} title="Toggle admin" testid="btn-role" />
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
  const [userSearch, setUserSearch] = useState("");
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
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>User Activity — search by user</h3>
        </div>
        <div className="relative mb-4">
          <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-muted-stitch" />
          <input data-testid="user-activity-search" value={userSearch} onChange={(e) => setUserSearch(e.target.value)}
            placeholder="Search members by name or email…" className="neu-input w-full rounded-2xl py-3 pl-12 pr-4" />
        </div>
        {userSearch.trim() && !selUser && (
          <div className="space-y-2 max-h-56 overflow-y-auto mb-2" data-testid="user-search-results">
            {users.filter((u) => `${u.name} ${u.email}`.toLowerCase().includes(userSearch.toLowerCase())).slice(0, 20).map((u) => (
              <button key={u.user_id} data-testid="user-search-result" onClick={() => loadUser(u.user_id)}
                className="w-full neu-pressed neu-hover rounded-2xl p-3 flex items-center gap-3 text-left">
                <Avatar u={u} />
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{u.name}</p>
                  <p className="text-xs text-muted-stitch truncate">{u.email}</p>
                </div>
              </button>
            ))}
            {users.filter((u) => `${u.name} ${u.email}`.toLowerCase().includes(userSearch.toLowerCase())).length === 0 && (
              <p className="text-sm text-muted-stitch p-2">No members match “{userSearch}”.</p>
            )}
          </div>
        )}
        {selUser && (
          <button data-testid="clear-user-selection" onClick={() => { setSelUser(""); setUserLogs(null); }}
            className="neu-btn rounded-full px-4 py-1.5 text-sm font-semibold text-primary-stitch mb-4">← Back to search</button>
        )}
        {!selUser && !userSearch.trim() && <p className="text-muted-stitch text-sm">Search for a member to trace exactly what they did and when.</p>}
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

function heatRamp() {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 1;
  const g = c.getContext("2d");
  const grad = g.createLinearGradient(0, 0, 256, 0);
  grad.addColorStop(0.0, "#1e3a8a");
  grad.addColorStop(0.4, "#06b6d4");
  grad.addColorStop(0.6, "#84cc16");
  grad.addColorStop(0.8, "#f59e0b");
  grad.addColorStop(1.0, "#dc2626");
  g.fillStyle = grad; g.fillRect(0, 0, 256, 1);
  const data = g.getImageData(0, 0, 256, 1).data;
  const ramp = [];
  for (let i = 0; i < 256; i++) ramp.push([data[i * 4], data[i * 4 + 1], data[i * 4 + 2]]);
  return ramp;
}

function HeatmapCanvas({ points }) {
  const ref = useRef(null);
  const W = 960, H = 540;
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, W, H);
    if (!points || !points.length) return;
    ctx.globalCompositeOperation = "lighter";
    points.forEach((p) => {
      const x = p.x * W, y = p.y * H, r = 26;
      const g = ctx.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, "rgba(0,0,0,0.20)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
    });
    ctx.globalCompositeOperation = "source-over";
    const img = ctx.getImageData(0, 0, W, H);
    const d = img.data;
    const ramp = heatRamp();
    for (let i = 0; i < d.length; i += 4) {
      const a = d[i + 3];
      if (a === 0) continue;
      const c = ramp[Math.min(255, a)];
      d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2];
      d[i + 3] = Math.min(235, a * 3);
    }
    ctx.putImageData(img, 0, 0);
  }, [points]);
  return <canvas ref={ref} width={W} height={H} data-testid="heatmap-canvas" className="absolute inset-0 w-full h-full" />;
}

function Sparkline({ data }) {
  const w = 560, h = 60, pad = 4;
  const max = Math.max(1, ...data.map((d) => d.clicks));
  const step = (w - 2 * pad) / Math.max(1, data.length - 1);
  const pts = data.map((d, i) => `${pad + i * step},${h - pad - (d.clicks / max) * (h - 2 * pad)}`).join(" ");
  const area = `${pad},${h - pad} ${pts} ${pad + (data.length - 1) * step},${h - pad}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="w-full" style={{ height: 60 }} data-testid="heatmap-sparkline">
      <polygon points={area} fill="var(--primary)" opacity="0.14" />
      <polyline points={pts} fill="none" stroke="var(--primary)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      {data.map((d, i) => (
        <circle key={i} cx={pad + i * step} cy={h - pad - (d.clicks / max) * (h - 2 * pad)} r="2" fill="var(--primary)" />
      ))}
    </svg>
  );
}

function HeatmapTab() {
  const [grid, setGrid] = useState(null);
  const [paths, setPaths] = useState(null);
  const [sel, setSel] = useState("");
  const [clicks, setClicks] = useState(null);
  const [refImg, setRefImg] = useState(null);
  const [clarityId, setClarityId] = useState("");
  const [range, setRange] = useState("all");
  const [trend, setTrend] = useState(null);

  useEffect(() => { api.get("/admin/heatmap").then(({ data }) => setGrid(data.grid)).catch(() => setGrid([[0]])); }, []);
  useEffect(() => { api.get("/admin/heatmap/trend").then(({ data }) => setTrend(data)).catch(() => setTrend(null)); }, []);
  useEffect(() => { api.get("/site-config").then(({ data }) => setClarityId(data.clarity_id || "")).catch(() => {}); }, []);
  useEffect(() => {
    api.get("/admin/heatmap/paths", { params: { range } }).then(({ data }) => {
      setPaths(data);
      setSel((prev) => (prev && data.paths.some((p) => p.path === prev)) ? prev : (data.paths[0]?.path || ""));
    }).catch(() => setPaths({ paths: [], visitors: 0, total_clicks: 0, total_views: 0 }));
  }, [range]);
  useEffect(() => {
    if (!sel) { setClicks(null); setRefImg(null); return; }
    setClicks(null); setRefImg(null);
    api.get("/admin/heatmap/clicks", { params: { path: sel, range } }).then(({ data }) => setClicks(data)).catch(() => setClicks({ points: [], top_elements: [], count: 0 }));
    api.get("/admin/heatmap/reference", { params: { path: sel } }).then(({ data }) => setRefImg(data.image || null)).catch(() => setRefImg(null));
  }, [sel, range]);

  if (!grid || !paths) return <Loader />;
  const max = Math.max(1, ...grid.flat());
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div className="space-y-6" data-testid="heatmap-tab">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="grid grid-cols-3 gap-5 flex-1 min-w-[18rem]">
          <StatCard label="Unique visitors" value={paths.visitors} />
          <StatCard label="Total clicks" value={paths.total_clicks} color="#dc2626" />
          <StatCard label="Page views" value={paths.total_views} />
        </div>
        {clarityId && (
          <a href={`https://clarity.microsoft.com/projects/view/${clarityId}/dashboard`} target="_blank" rel="noreferrer"
            data-testid="open-clarity-btn" className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2 shrink-0">
            <Activity className="w-4 h-4" /> Open Microsoft Clarity
          </a>
        )}
      </div>

      {trend && (
        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="heatmap-trend-card">
          <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
            <h3 className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>Clicks — last 14 days</h3>
            <span className="text-sm text-muted-stitch">{trend.total} total</span>
          </div>
          <Sparkline data={trend.days} />
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-muted-stitch">{trend.days[0]?.d}</span>
            <span className="text-[10px] text-muted-stitch">{trend.days[trend.days.length - 1]?.d}</span>
          </div>
        </div>
      )}

      <div className="neu-pressed rounded-full p-1.5 flex gap-1 w-fit" data-testid="heatmap-range">
        {[["24h", "Last 24h"], ["7d", "7 days"], ["30d", "30 days"], ["all", "All time"]].map(([id, lbl]) => (
          <button key={id} data-testid={`heatmap-range-${id}`} onClick={() => setRange(id)}
            className={`rounded-full py-2 px-4 text-sm font-semibold whitespace-nowrap ${range === id ? "neu-primary" : "text-muted-stitch"}`}>{lbl}</button>
        ))}
      </div>

      <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up">
        <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Site click heatmap</h3>
            <p className="text-sm text-muted-stitch">Where visitors and users click across the whole site. Public pages show the real page behind the heat.</p>
          </div>
          <select data-testid="heatmap-path-select" value={sel} onChange={(e) => setSel(e.target.value)}
            className="neu-input rounded-2xl py-2.5 px-4 text-sm max-w-[16rem]">
            {paths.paths.length === 0 && <option value="">No data yet</option>}
            {paths.paths.map((p) => (
              <option key={p.path} value={p.path}>{p.path} ({p.clicks} clicks)</option>
            ))}
          </select>
        </div>
        {paths.paths.length === 0 ? (
          <p className="text-sm text-muted-stitch mt-4" data-testid="heatmap-empty">No activity recorded yet. Browse the site to generate click data — it appears here within a few seconds.</p>
        ) : !clicks ? (
          <div className="py-10"><Loader /></div>
        ) : (
          <div className="grid lg:grid-cols-3 gap-6 mt-4">
            <div className="lg:col-span-2">
              <div className="relative w-full rounded-2xl overflow-hidden" style={{ aspectRatio: "16 / 9", background: "var(--neu-dark)" }}>
                {refImg && <img src={refImg} alt="page reference" className="absolute inset-0 w-full h-full object-cover object-top opacity-70" data-testid="heatmap-ref-img" />}
                <HeatmapCanvas points={clicks.points} />
              </div>
              <p className="text-xs text-muted-stitch mt-2">{clicks.count} click(s) on <span className="font-semibold">{sel}</span> · blue = light, red = hot{refImg ? " · overlaid on the live page" : ""}</p>
            </div>
            <div>
              <p className="text-sm font-semibold mb-3" style={{ color: "var(--text)" }}>Most clicked elements</p>
              {clicks.top_elements.length === 0 ? (
                <p className="text-xs text-muted-stitch">No labelled clicks yet.</p>
              ) : (
                <div className="space-y-2" data-testid="heatmap-top-elements">
                  {clicks.top_elements.map((t, i) => (
                    <div key={i} className="neu-pressed rounded-xl p-3 flex items-center justify-between gap-2">
                      <span className="text-xs truncate" style={{ color: "var(--text)" }}>{t.label}</span>
                      <span className="text-xs font-bold text-primary-stitch shrink-0">{t.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up overflow-x-auto">
        <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>Activity by time</h3>
        <p className="text-sm text-muted-stitch mb-6">Event intensity by day of week and hour (UTC).</p>
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

function IntegrationsTab() {
  const [items, setItems] = useState(null);
  const [goog, setGoog] = useState(null);
  const [savingG, setSavingG] = useState(false);
  const [dl, setDl] = useState(null);
  const [savingDl, setSavingDl] = useState(false);
  useEffect(() => {
    api.get("/admin/integrations").then(({ data }) => setItems(data)).catch(() => setItems([]));
    api.get("/admin/google-oauth").then(({ data }) => setGoog(data)).catch(() => setGoog({ client_id: "", client_secret: "", redirect_uri: "" }));
    api.get("/admin/downloads-config").then(({ data }) => setDl(data)).catch(() => setDl({ repo: "" }));
  }, []);
  const saveGoogle = async () => {
    setSavingG(true);
    try {
      await api.put("/admin/google-oauth", { client_id: goog.client_id, client_secret: goog.client_secret });
      toast.success("Google credentials saved");
      const { data } = await api.get("/admin/google-oauth"); setGoog(data);
    } catch (e) { toast.error("Save failed"); } finally { setSavingG(false); }
  };
  const saveDl = async () => {
    setSavingDl(true);
    try {
      await api.put("/admin/downloads-config", { repo: dl.repo });
      toast.success("Desktop release repository saved");
    } catch (e) { toast.error("Save failed"); } finally { setSavingDl(false); }
  };
  if (!items || !goog || !dl) return <Loader />;
  return (
    <div className="space-y-6">
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="desktop-release-card">
        <div className="flex items-center gap-3 mb-2">
          <div className="neu-sm w-10 h-10 rounded-2xl flex items-center justify-center"><Download className="w-5 h-5 text-primary-stitch" /></div>
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Desktop app releases</h3>
        </div>
        <p className="text-sm text-muted-stitch mb-4">Set the GitHub repository that publishes the desktop installers (built by the CI workflow on <span className="font-mono-stitch">v*</span> tags). The Downloads page buttons will link to the latest release assets automatically.</p>
        <label className="text-sm font-semibold text-muted-stitch">Repository (owner/repo)</label>
        <input data-testid="desktop-repo-input" value={dl.repo || ""} placeholder="your-org/stitches-desktop"
          onChange={(e) => setDl({ ...dl, repo: e.target.value })} className="neu-input w-full rounded-2xl py-3 px-5 mt-2 font-mono-stitch" />
        <button data-testid="save-desktop-repo" onClick={saveDl} disabled={savingDl} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingDl ? "Saving…" : "Save repository"}</button>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="google-oauth-card">
        <div className="flex items-center gap-3 mb-2">
          <div className="neu-sm w-10 h-10 rounded-2xl flex items-center justify-center"><Plug className="w-5 h-5 text-primary-stitch" /></div>
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Google Drive OAuth</h3>
        </div>
        <p className="text-sm text-muted-stitch mb-4">Editable credentials for the one-click "Connect with Google" flow. Add the redirect URI below to your Google Cloud OAuth app.</p>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-semibold text-muted-stitch">Client ID</label>
            <input data-testid="google-client-id" value={goog.client_id || ""} onChange={(e) => setGoog({ ...goog, client_id: e.target.value })} className="neu-input w-full rounded-2xl py-3 px-5 mt-2" />
          </div>
          <div>
            <label className="text-sm font-semibold text-muted-stitch">Client Secret</label>
            <input data-testid="google-client-secret" type="password" value={goog.client_secret || ""} onChange={(e) => setGoog({ ...goog, client_secret: e.target.value })} className="neu-input w-full rounded-2xl py-3 px-5 mt-2" />
          </div>
        </div>
        <div className="mt-4">
          <label className="text-sm font-semibold text-muted-stitch">Authorized redirect URI (add this in Google Cloud)</label>
          <div className="neu-pressed rounded-2xl py-3 px-5 mt-2 font-mono-stitch text-sm break-all" style={{ color: "var(--text)" }}>{goog.redirect_uri}</div>
        </div>
        <button data-testid="save-google-oauth" onClick={saveGoogle} disabled={savingG} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingG ? "Saving…" : "Save credentials"}</button>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="admin-connect-integrations">
        <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>Connect an application</h3>
        <p className="text-sm text-muted-stitch mb-5">Set up your own integrations here — nothing is forced, connect only what you need. The same catalog and wizard as the user dashboard.</p>
        <IntegrationsManager />
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <p className="text-muted-stitch mb-6">All integrations connected by members across the platform. Credentials are never exposed here.</p>
        {items.length === 0 ? (
          <p className="text-sm text-muted-stitch">No integrations connected yet.</p>
        ) : (
          <div className="space-y-3">
            {items.map((it) => (
              <div key={it.integration_id} className="neu-pressed rounded-2xl p-4 flex items-center gap-4" data-testid="admin-integration-row">
              <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0"><Plug className="w-5 h-5 text-primary-stitch" /></div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{it.name}</p>
                <p className="text-sm text-muted-stitch truncate">{it.type} · owned by {it.owner_name}</p>
              </div>
              <span className="text-xs px-3 py-1 rounded-full neu-sm text-green-500 font-semibold">{it.status || "connected"}</span>
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}


function SupportTab() {
  const [data, setData] = useState(null);
  const [reqs, setReqs] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [filter, setFilter] = useState("open"); // open | resolved | all
  const PAGE = 20;

  const fetchPage = (skip, append) => {
    return api.get("/admin/support-requests", { params: { status: filter, limit: PAGE, skip } }).then(({ data }) => {
      setData(data); setHasMore(data.has_more);
      setReqs((prev) => (append ? [...prev, ...data.requests] : data.requests));
    }).catch(() => { setData({ open_count: 0, total: 0 }); setReqs([]); setHasMore(false); });
  };
  const load = () => fetchPage(0, false);
  useEffect(() => { load(); }, [filter]); // eslint-disable-line

  const setStatus = async (r, resolved) => {
    try {
      await api.post(`/admin/support-requests/${r.request_id}/status`, { resolved });
      toast.success(resolved ? "Marked resolved" : "Reopened");
      load();
    } catch (e) { toast.error("Update failed"); }
  };

  if (!data) return <Loader />;
  const FILTERS = [["open", "Open"], ["resolved", "Resolved"], ["all", "All"]];
  return (
    <div className="space-y-6" data-testid="support-tab">
      <div className="grid grid-cols-2 gap-5">
        <StatCard label="Open requests" value={data.open_count} color={data.open_count > 0 ? "#dc2626" : "#16a34a"} />
        <StatCard label="Total requests" value={data.total} />
      </div>
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Support inbox</h3>
            <p className="text-sm text-muted-stitch">Help requests escalated by Stitch AI. Reply by email, then mark resolved.</p>
          </div>
          <button data-testid="support-refresh" onClick={load} className="neu-btn rounded-xl px-4 py-2 text-sm font-semibold text-primary-stitch">Refresh</button>
        </div>
        <div className="neu-pressed rounded-full p-1.5 flex gap-1 mb-5 w-fit">
          {FILTERS.map(([id, lbl]) => (
            <button key={id} data-testid={`support-filter-${id}`} onClick={() => setFilter(id)}
              className={`rounded-full py-2 px-5 text-sm font-semibold ${filter === id ? "neu-primary" : "text-muted-stitch"}`}>{lbl}</button>
          ))}
        </div>
        {reqs.length === 0 ? (
          <p className="text-sm text-muted-stitch" data-testid="support-empty">No {filter === "all" ? "" : filter} support requests.</p>
        ) : (
          <>
            <div className="space-y-3">
              {reqs.map((r) => (
                <div key={r.request_id} data-testid="support-row" className="neu-pressed rounded-2xl p-4">
                  <div className="flex items-start gap-3 flex-wrap">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-bold truncate" style={{ color: "var(--text)" }}>{r.subject}</p>
                        <span className={`text-[11px] px-2 py-0.5 rounded-full neu-sm font-semibold ${r.status === "resolved" ? "text-green-500" : "text-amber-500"}`}>{r.status}</span>
                      </div>
                      <p className="text-sm text-muted-stitch mt-1 whitespace-pre-line">{r.message}</p>
                      <p className="text-xs text-muted-stitch mt-2">{r.user_name} &lt;{r.user_email}&gt; · {new Date(r.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {r.user_email && (
                        <a data-testid="support-reply" href={`mailto:${r.user_email}?subject=${encodeURIComponent("Re: " + r.subject)}`}
                          className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold text-primary-stitch flex items-center gap-1.5"><Mail className="w-4 h-4" /> Reply</a>
                      )}
                      {r.status === "resolved" ? (
                        <button data-testid="support-reopen" onClick={() => setStatus(r, false)} className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold">Reopen</button>
                      ) : (
                        <button data-testid="support-resolve" onClick={() => setStatus(r, true)} className="neu-primary rounded-xl px-3 py-2 text-sm font-semibold flex items-center gap-1.5"><Check className="w-4 h-4" /> Resolve</button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {hasMore && (
              <button data-testid="support-load-more" onClick={() => fetchPage(reqs.length, true)} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch mt-5 w-full">Load more</button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function SiteNoteTab() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    api.get("/admin/site-config").then(({ data }) => setCfg({ announcement: { enabled: true, title: "", message: "", signature: "", ...data.announcement }, support_email: data.support_email || "", clarity_id: data.clarity_id || "", require_verification: !!data.require_verification }))
      .catch(() => setCfg({ announcement: { enabled: false, title: "", message: "", signature: "" }, support_email: "", clarity_id: "", require_verification: false }));
  }, []);
  const setAnn = (k, v) => setCfg((c) => ({ ...c, announcement: { ...c.announcement, [k]: v } }));

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/admin/site-config", { announcement: cfg.announcement, support_email: cfg.support_email, clarity_id: cfg.clarity_id, require_verification: cfg.require_verification });
      toast.success("Site settings saved");
    } catch (e) { toast.error("Save failed"); } finally { setSaving(false); }
  };

  if (!cfg) return <Loader />;
  const a = cfg.announcement;
  return (
    <div className="space-y-6" data-testid="sitenote-tab">
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="announcement-card">
        <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Megaphone className="w-5 h-5 text-primary-stitch" /></div>
            <div>
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Home page note</h3>
              <p className="text-sm text-muted-stitch">The glass card shown to visitors on the landing page. Toggle it on or off any time.</p>
            </div>
          </div>
          <button data-testid="announcement-enabled-toggle" aria-pressed={a.enabled} data-state={a.enabled ? "on" : "off"} onClick={() => setAnn("enabled", !a.enabled)}
            className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${a.enabled ? "justify-end" : "justify-start"}`}
            style={{ background: a.enabled ? "var(--primary)" : "var(--neu-dark)" }}>
            <span className="w-6 h-6 rounded-full bg-white shadow" />
          </button>
        </div>
        <div className="space-y-3 mt-4">
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Title</label>
            <input data-testid="announcement-title-input" value={a.title} onChange={(e) => setAnn("title", e.target.value)} placeholder="Hello, and welcome" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Message</label>
            <textarea data-testid="announcement-message-input" value={a.message} onChange={(e) => setAnn("message", e.target.value)} rows={4} placeholder="Your welcome message…" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 resize-none" />
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Signature</label>
            <input data-testid="announcement-signature-input" value={a.signature} onChange={(e) => setAnn("signature", e.target.value)} placeholder="— The Development team" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
          </div>
        </div>
        <p className="text-xs text-muted-stitch mt-3">Editing the note re-shows it to everyone (even visitors who dismissed the previous version).</p>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="support-email-card">
        <div className="flex items-center gap-3 mb-1">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Bell className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Support email</h3>
            <p className="text-sm text-muted-stitch">Where Stitch AI forwards help requests it can't resolve. Update it any time.</p>
          </div>
        </div>
        <input data-testid="support-email-input" value={cfg.support_email} onChange={(e) => setCfg({ ...cfg, support_email: e.target.value })} placeholder="support@yourco.com" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-4" />
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="clarity-card">
        <div className="flex items-center gap-3 mb-1">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Activity className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Microsoft Clarity</h3>
            <p className="text-sm text-muted-stitch">Project ID used for the "Open Clarity" deep-link in the Heat Map tab.</p>
          </div>
        </div>
        <input data-testid="clarity-id-input" value={cfg.clarity_id} onChange={(e) => setCfg({ ...cfg, clarity_id: e.target.value })} placeholder="xnf9nc40tt" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-4 font-mono-stitch" />
      </div>

      <EmailSetupWizard />

      <EmailAnalyticsCard />

      <TestEmailCard />

      <DigestCard />

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="require-verification-card">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><ShieldCheck className="w-5 h-5 text-primary-stitch" /></div>
            <div>
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Require email verification</h3>
              <p className="text-sm text-muted-stitch">When ON, unverified users can't create meetings until they confirm their email. Keep OFF until email delivery is working.</p>
            </div>
          </div>
          <button data-testid="require-verification-toggle" onClick={() => setCfg({ ...cfg, require_verification: !cfg.require_verification })}
            className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${cfg.require_verification ? "justify-end" : "justify-start"}`}
            style={{ background: cfg.require_verification ? "var(--primary)" : "var(--neu-dark)" }}>
            <span className="w-6 h-6 rounded-full bg-white shadow" />
          </button>
        </div>
      </div>

      <button data-testid="save-sitenote-btn" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold">{saving ? "Saving…" : "Save site settings"}</button>
    </div>
  );
}

const DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function CopyRow({ value, testid }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); toast.success("Copied"); setTimeout(() => setCopied(false), 1500); }
    catch (e) { toast.error("Copy failed"); }
  };
  return (
    <div className="neu-pressed rounded-xl flex items-center gap-2 pl-3 pr-1.5 py-1.5 mt-1">
      <span data-testid={testid} className="font-mono-stitch text-xs break-all flex-1" style={{ color: "var(--text)" }}>{value}</span>
      <button data-testid={`${testid}-copy`} onClick={copy} className="neu-btn rounded-lg px-3 py-1.5 text-xs font-semibold text-primary-stitch shrink-0">{copied ? "Copied ✓" : "Copy"}</button>
    </div>
  );
}

function EmailAnalyticsCard() {
  const [data, setData] = useState(null);
  const load = () => api.get("/admin/email-events").then(({ data }) => setData(data)).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);
  const unsuppress = async (email) => {
    try { await api.post("/admin/email-events/unsuppress", { email }); toast.success("Removed from suppression"); load(); }
    catch (e) { toast.error("Failed"); }
  };
  if (!data) return null;
  const stat = (label, val, sub) => (
    <div className="neu-pressed rounded-2xl p-4 text-center">
      <p className="text-2xl font-head font-bold" style={{ color: "var(--text)" }}>{val}</p>
      <p className="text-xs text-muted-stitch mt-1">{label}{sub ? ` · ${sub}` : ""}</p>
    </div>
  );
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="email-analytics-card">
      <div className="flex items-center gap-3 mb-4">
        <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Activity className="w-5 h-5 text-primary-stitch" /></div>
        <div>
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Email delivery</h3>
          <p className="text-sm text-muted-stitch">Live stats from Mailgun webhooks. Bounced/complained addresses are auto-suppressed.</p>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stat("Delivered", data.delivered, `${data.delivery_rate}%`)}
        {stat("Opened", data.opened, `${data.open_rate}%`)}
        {stat("Bounced", data.bounced)}
        {stat("Suppressed", (data.suppressed || []).length)}
      </div>
      {(data.suppressed || []).length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-muted-stitch mb-2">Suppressed addresses</p>
          <div className="space-y-2 max-h-52 overflow-y-auto">
            {data.suppressed.map((s, i) => (
              <div key={i} data-testid="suppressed-row" className="neu-pressed rounded-2xl px-4 py-2.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>{s.email}</p>
                  <p className="text-xs text-muted-stitch truncate">{s.reason}{s.detail ? ` · ${s.detail}` : ""}</p>
                </div>
                <button data-testid="unsuppress-btn" onClick={() => unsuppress(s.email)} className="neu-btn rounded-lg px-3 py-1.5 text-xs font-semibold text-primary-stitch shrink-0">Restore</button>
              </div>
            ))}
          </div>
        </div>
      )}
      {data.recent && data.recent.length > 0 && (
        <p className="text-xs text-muted-stitch mt-4">Last event: {data.recent[0].event} → {data.recent[0].recipient} ({new Date(data.recent[0].created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })})</p>
      )}
    </div>
  );
}

function EmailSetupWizard() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [smtp, setSmtp] = useState(null);
  const [savingSmtp, setSavingSmtp] = useState(false);
  const [saJson, setSaJson] = useState("");
  const [savingSa, setSavingSa] = useState(false);
  const [mg, setMg] = useState(null);
  const [savingMg, setSavingMg] = useState(false);
  const [dns, setDns] = useState(null);
  const [checkingDns, setCheckingDns] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const load = () => {
    api.get("/admin/email-provider").then(({ data }) => setCfg(data)).catch(() => {});
    api.get("/admin/smtp-config").then(({ data }) => setSmtp(data)).catch(() => setSmtp({ enabled: false, host: "", port: 587, username: "", from_address: "", has_password: false }));
    api.get("/admin/mailgun-config").then(({ data }) => setMg({ ...data, api_key: "" })).catch(() => setMg({ domain: "", region: "US", sender: "", api_key: "", has_api_key: false }));
  };
  useEffect(() => {
    load();
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail") === "connected") { toast.success("Gmail connected"); window.history.replaceState({}, "", window.location.pathname); }
    else if (params.get("gmail") === "error") { toast.error("Gmail connection failed — check Google Cloud setup"); window.history.replaceState({}, "", window.location.pathname); }
  }, []);

  const saveProvider = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/admin/email-provider", { provider: cfg.provider, sender: cfg.sender, resend_fallback: cfg.resend_fallback });
      setCfg((c) => ({ ...c, ...data }));
      toast.success("Email settings saved");
    } catch (e) { toast.error("Save failed"); } finally { setSaving(false); }
  };

  const connectGmail = async () => {
    setConnecting(true);
    try {
      const { data } = await api.get("/admin/gmail/authorize");
      window.location.href = data.authorization_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not start Google connection"); setConnecting(false); }
  };
  const disconnectGmail = async () => {
    try { await api.post("/admin/gmail/disconnect"); toast.success("Gmail disconnected"); load(); }
    catch (e) { toast.error("Failed to disconnect"); }
  };
  const saveSmtp = async () => {
    setSavingSmtp(true);
    try {
      await api.put("/admin/smtp-config", { enabled: true, host: smtp.host, port: smtp.port, username: smtp.username, from_address: smtp.from_address, password: smtp.password || "" });
      toast.success("SMTP saved");
      load();
    } catch (e) { toast.error("Save failed"); } finally { setSavingSmtp(false); }
  };

  const saveMg = async () => {
    setSavingMg(true);
    try {
      await api.put("/admin/mailgun-config", { enabled: true, domain: mg.domain, region: mg.region, sender: mg.sender, api_key: mg.api_key || "", webhook_signing_key: mg.webhook_signing_key || "" });
      toast.success("Mailgun saved");
      load();
    } catch (e) { toast.error("Save failed"); } finally { setSavingMg(false); }
  };

  const checkDns = async () => {
    setCheckingDns(true); setDns(null);
    try {
      const { data } = await api.get("/admin/mailgun/dns");
      setDns(data);
      if (!data.ok) toast.error(data.error || "DNS check failed");
    } catch (e) { toast.error("DNS check failed"); } finally { setCheckingDns(false); }
  };

  const saveSa = async () => {
    if (!saJson.trim()) { toast.error("Paste the service account JSON first"); return; }
    setSavingSa(true);
    try {
      const { data } = await api.put("/admin/gmail/service-account", { service_account_json: saJson });
      toast.success(`Service account saved (${data.client_email})`);
      setSaJson("");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Invalid service account JSON"); } finally { setSavingSa(false); }
  };
  const disconnectSa = async () => {
    try { await api.post("/admin/gmail/service-account/disconnect"); toast.success("Service account removed"); load(); }
    catch (e) { toast.error("Failed to remove"); }
  };

  const sendTest = async () => {
    setTesting(true); setTestResult(null);
    try {
      const { data } = await api.post("/admin/test-email", { to: cfg.sender || undefined });
      setTestResult(data);
      toast[data.ok ? "success" : "error"](data.ok ? `Sent to ${data.to}` : "Send failed");
    } catch (e) { toast.error("Request failed"); } finally { setTesting(false); }
  };

  if (!cfg || !smtp || !mg) return null;
  const g = cfg.gmail || {};
  const sa = cfg.gmail_sa || {};
  const mgStatus = cfg.mailgun || {};
  const webhookUrl = `${process.env.REACT_APP_BACKEND_URL}/api/webhooks/mailgun`;
  const providerBtn = (id, label, sub) => (
    <button data-testid={`email-provider-${id}`} onClick={() => setCfg({ ...cfg, provider: id })}
      className={`flex-1 text-left rounded-2xl p-4 transition-all ${cfg.provider === id ? "neu-primary" : "neu-pressed"}`}>
      <p className={`font-head font-bold ${cfg.provider === id ? "text-white" : ""}`} style={cfg.provider === id ? {} : { color: "var(--text)" }}>{label}</p>
      <p className={`text-xs mt-0.5 ${cfg.provider === id ? "text-white/80" : "text-muted-stitch"}`}>{sub}</p>
    </button>
  );

  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="email-setup-wizard">
      <div className="flex items-center gap-3 mb-1">
        <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Mail className="w-5 h-5 text-primary-stitch" /></div>
        <div>
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Email setup</h3>
          <p className="text-sm text-muted-stitch">Choose how Stitches sends email (invites, digests, alerts). No domain verification needed.</p>
        </div>
      </div>

      <p className="text-xs font-semibold text-muted-stitch mt-4 mb-2">Step 1 — Choose a provider</p>
      <div className="flex gap-3 flex-wrap">
        {providerBtn("mailgun", "Mailgun", "API-based. Sends to anyone with a verified domain. Recommended.")}
        {providerBtn("gmail_sa", "Gmail (service account)", "Google service account + domain-wide delegation.")}
        {providerBtn("gmail", "Gmail (OAuth)", "Connect a Google account with one click.")}
        {providerBtn("smtp", "SMTP", "Any mailbox: Gmail app-password, Outlook, or your own server.")}
      </div>

      <p className="text-xs font-semibold text-muted-stitch mt-6 mb-2">Step 2 — Configure</p>
      {cfg.provider === "mailgun" ? (
        <div className="neu-pressed rounded-2xl p-4" data-testid="mailgun-config">
          {mgStatus.configured && <p className="text-sm mb-3" style={{ color: "var(--text)" }}>✓ Mailgun configured for <span className="font-semibold" data-testid="mailgun-domain">{mgStatus.domain}</span> ({mgStatus.region})</p>}
          <div className="grid sm:grid-cols-2 gap-3">
            <input data-testid="mailgun-domain-input" value={mg.domain} onChange={(e) => setMg({ ...mg, domain: e.target.value })} placeholder="mg.yourdomain.com" className="neu-input rounded-2xl py-3 px-4 text-sm" />
            <select data-testid="mailgun-region" value={mg.region} onChange={(e) => setMg({ ...mg, region: e.target.value })} className="neu-input rounded-2xl py-3 px-4 text-sm">
              <option value="US">US (api.mailgun.net)</option>
              <option value="EU">EU (api.eu.mailgun.net)</option>
            </select>
            <input data-testid="mailgun-apikey" type="password" value={mg.api_key} onChange={(e) => setMg({ ...mg, api_key: e.target.value })} placeholder={mg.has_api_key ? "•••••• (saved)" : "Mailgun API key"} className="neu-input rounded-2xl py-3 px-4 text-sm" />
            <input data-testid="mailgun-sender" value={mg.sender} onChange={(e) => setMg({ ...mg, sender: e.target.value })} placeholder="noreply@mg.yourdomain.com" className="neu-input rounded-2xl py-3 px-4 text-sm" />
            <input data-testid="mailgun-webhook-key" type="password" value={mg.webhook_signing_key || ""} onChange={(e) => setMg({ ...mg, webhook_signing_key: e.target.value })} placeholder={mgStatus.has_webhook_key ? "•••••• webhook key (saved)" : "Webhook signing key (optional — for delivery tracking)"} className="neu-input rounded-2xl py-3 px-4 text-sm sm:col-span-2" />
          </div>
          <button data-testid="save-mailgun-btn" onClick={saveMg} disabled={savingMg} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingMg ? "Saving…" : "Save Mailgun"}</button>
          <div className="mt-4">
            <label className="text-xs font-semibold text-muted-stitch">Webhook URL (paste into Mailgun → Webhooks)</label>
            <CopyRow value={webhookUrl} testid="mailgun-webhook-url" />
          </div>
          <div className="mt-4 flex items-center gap-3 flex-wrap">
            <button data-testid="check-dns-btn" onClick={checkDns} disabled={checkingDns} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch">{checkingDns ? "Checking…" : "Check DNS"}</button>
            {dns && dns.ok && (
              <span data-testid="dns-state" className={`text-sm font-semibold ${dns.all_valid ? "text-green-500" : "text-amber-500"}`}>
                Domain state: {dns.state || "unknown"}{dns.all_valid ? " · all records valid ✓" : " · records pending"}
              </span>
            )}
          </div>
          {dns && dns.ok && (dns.sending || []).length > 0 && (
            <div className="mt-3 space-y-2" data-testid="dns-checklist">
              {dns.sending.map((r, i) => (
                <div key={i} data-testid="dns-record-row" className="neu-pressed rounded-2xl px-4 py-2.5 flex items-center gap-3">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: r.valid ? "#16a34a" : "#ef4444", boxShadow: `0 0 8px ${r.valid ? "#16a34a" : "#ef4444"}` }} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold" style={{ color: "var(--text)" }}>{r.type} · {r.name}</p>
                    <p className="text-xs text-muted-stitch font-mono-stitch break-all">{r.value}</p>
                  </div>
                  <span className={`text-xs font-bold shrink-0 ${r.valid ? "text-green-500" : "text-red-400"}`}>{r.valid ? "Valid" : "Missing"}</span>
                </div>
              ))}
            </div>
          )}
          <p className="text-xs text-muted-stitch mt-3">Get API key + domain at Mailgun → Sending → Domains → Domain settings. Add the webhook URL under Sending → Webhooks (delivered, opened, permanent failure, complained) to see delivery stats below. Sandbox domains only send to authorized recipients.</p>
        </div>
      ) : cfg.provider === "gmail_sa" ? (
        <div className="neu-pressed rounded-2xl p-4" data-testid="gmail-sa-config">
          {sa.connected ? (
            <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
              <p className="text-sm" style={{ color: "var(--text)" }}>✓ Service account: <span className="font-semibold font-mono-stitch text-xs" data-testid="gmail-sa-email">{sa.client_email}</span></p>
              <button data-testid="gmail-sa-disconnect-btn" onClick={disconnectSa} className="neu-btn rounded-xl px-4 py-2 text-sm font-semibold text-red-500">Remove</button>
            </div>
          ) : (
            <p className="text-sm text-muted-stitch mb-3">Paste a Google service account JSON key below.</p>
          )}
          <textarea data-testid="gmail-sa-json" value={saJson} onChange={(e) => setSaJson(e.target.value)} rows={4}
            placeholder='{ "type": "service_account", "project_id": "...", "private_key": "...", "client_email": "...@...iam.gserviceaccount.com", ... }'
            className="neu-input w-full rounded-2xl py-3 px-4 text-xs font-mono-stitch resize-none" />
          <button data-testid="save-gmail-sa-btn" onClick={saveSa} disabled={savingSa} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-3">{savingSa ? "Saving…" : sa.connected ? "Replace key" : "Save service account"}</button>
          <p className="text-xs text-muted-stitch mt-3">Requires <b>domain-wide delegation</b> in Google Workspace: authorize client ID <span className="font-mono-stitch">{sa.client_id || "(the service account's client id)"}</span> for scope <span className="font-mono-stitch">https://www.googleapis.com/auth/gmail.send</span>, and the sender below must be a Workspace user.</p>
        </div>
      ) : cfg.provider === "gmail" ? (
        <div className="neu-pressed rounded-2xl p-4" data-testid="gmail-config">
          {!g.configured ? (
            <p className="text-sm text-red-400">Google OAuth credentials are not configured on the server. Add <span className="font-mono-stitch">GOOGLE_CLIENT_ID</span> / <span className="font-mono-stitch">GOOGLE_CLIENT_SECRET</span> and enable the Gmail API.</p>
          ) : g.connected ? (
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <p className="text-sm" style={{ color: "var(--text)" }}>✓ Connected as <span className="font-semibold" data-testid="gmail-connected-email">{g.email || "Google account"}</span></p>
              <button data-testid="gmail-disconnect-btn" onClick={disconnectGmail} className="neu-btn rounded-xl px-4 py-2 text-sm font-semibold text-red-500">Disconnect</button>
            </div>
          ) : (
            <div>
              <p className="text-sm text-muted-stitch mb-3">Authorize a Google account so Stitches can send email on your behalf.</p>
              <button data-testid="gmail-connect-btn" onClick={connectGmail} disabled={connecting} className="neu-primary rounded-2xl px-6 py-3 font-semibold">{connecting ? "Redirecting…" : "Connect Google account"}</button>
              <p className="text-xs text-muted-stitch mt-3">Add this redirect URI in Google Cloud → Credentials:</p>
              <CopyRow value={g.redirect_uri} testid="gmail-redirect-uri" />
            </div>
          )}
        </div>
      ) : (
        <div className="neu-pressed rounded-2xl p-4" data-testid="smtp-config-wizard">
          <div className="grid sm:grid-cols-2 gap-3">
            <input data-testid="wiz-smtp-host" value={smtp.host} onChange={(e) => setSmtp({ ...smtp, host: e.target.value })} placeholder="smtp.gmail.com" className="neu-input rounded-2xl py-3 px-4 text-sm" />
            <input data-testid="wiz-smtp-port" type="number" value={smtp.port} onChange={(e) => setSmtp({ ...smtp, port: e.target.value })} placeholder="587" className="neu-input rounded-2xl py-3 px-4 text-sm" />
            <input data-testid="wiz-smtp-username" value={smtp.username} onChange={(e) => setSmtp({ ...smtp, username: e.target.value })} placeholder="you@gmail.com" className="neu-input rounded-2xl py-3 px-4 text-sm" />
            <input data-testid="wiz-smtp-password" type="password" value={smtp.password || ""} onChange={(e) => setSmtp({ ...smtp, password: e.target.value })} placeholder={smtp.has_password ? "•••••• (saved)" : "app password"} className="neu-input rounded-2xl py-3 px-4 text-sm" />
            <input data-testid="wiz-smtp-from" value={smtp.from_address} onChange={(e) => setSmtp({ ...smtp, from_address: e.target.value })} placeholder="from address" className="neu-input rounded-2xl py-3 px-4 text-sm sm:col-span-2" />
          </div>
          <button data-testid="wiz-save-smtp" onClick={saveSmtp} disabled={savingSmtp} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingSmtp ? "Saving…" : "Save SMTP"}</button>
        </div>
      )}

      <p className="text-xs font-semibold text-muted-stitch mt-6 mb-2">Step 3 — Default sender & fallback</p>
      <div>
        <label className="text-xs font-semibold text-muted-stitch">Sender / "from" address</label>
        <input data-testid="email-sender-input" value={cfg.sender} onChange={(e) => setCfg({ ...cfg, sender: e.target.value })} placeholder="admin@godesk.io" className="neu-input rounded-2xl py-3 px-4 text-sm w-full mt-1" />
      </div>
      <div className="neu-pressed rounded-2xl p-4 flex items-center justify-between mt-3">
        <div className="min-w-0 pr-3">
          <span className="font-medium text-sm" style={{ color: "var(--text)" }}>Use Resend as fallback</span>
          <p className="text-xs text-muted-stitch mt-0.5">Off by default. Only used if your primary provider fails{cfg.resend_available ? "" : " (Resend keys not present)"}.</p>
        </div>
        <button data-testid="resend-fallback-toggle" onClick={() => setCfg({ ...cfg, resend_fallback: !cfg.resend_fallback })}
          className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${cfg.resend_fallback ? "justify-end" : "justify-start"}`}
          style={{ background: cfg.resend_fallback ? "var(--primary)" : "var(--neu-dark)" }}>
          <span className="w-6 h-6 rounded-full bg-white shadow" />
        </button>
      </div>

      <div className="mt-4 flex items-center gap-3 flex-wrap">
        <button data-testid="save-email-provider-btn" onClick={saveProvider} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold">{saving ? "Saving…" : "Save email settings"}</button>
        <button data-testid="wizard-send-test-btn" onClick={sendTest} disabled={testing} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch">{testing ? "Sending…" : "Send test email"}</button>
      </div>
      {testResult && (
        <div data-testid="wizard-test-result" className={`neu-pressed rounded-2xl p-4 mt-4 text-sm ${testResult.ok ? "text-green-500" : "text-red-400"}`}>
          {testResult.ok ? "✓ " : "✕ "}{testResult.detail}
        </div>
      )}
    </div>
  );
}


function DigestCard() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [result, setResult] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [history, setHistory] = useState([]);

  const loadHistory = () => api.get("/admin/digest/history").then(({ data }) => setHistory(data.history || [])).catch(() => {});

  useEffect(() => {
    api.get("/admin/digest-config").then(({ data }) => setCfg(data))
      .catch(() => setCfg({ enabled: false, frequency: "weekly", day_of_week: 0, day_of_month: 1, hour: 9, recipient: "admin@godesk.io", last_sent: "" }));
    loadHistory();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/admin/digest-config", cfg);
      setCfg(data);
      toast.success("Digest schedule saved");
    } catch (e) { toast.error("Save failed"); } finally { setSaving(false); }
  };

  const sendNow = async () => {
    setSending(true); setResult(null);
    try {
      const { data } = await api.post("/admin/digest/send-now", { frequency: cfg.frequency, recipient: cfg.recipient });
      setResult(data);
      loadHistory();
      toast[data.ok ? "success" : "error"](data.ok ? "Digest sent" : "Send failed");
    } catch (e) { toast.error("Request failed"); } finally { setSending(false); }
  };

  const sendReport = async () => {
    setReporting(true); setResult(null);
    try {
      const { data } = await api.post("/admin/digest/send-report", { recipient: cfg.recipient });
      setResult(data);
      loadHistory();
      toast[data.ok ? "success" : "error"](data.ok ? "Full report sent" : "Send failed");
    } catch (e) { toast.error("Request failed"); } finally { setReporting(false); }
  };

  const togglePreview = async () => {
    if (preview) { setPreview(null); return; }
    setLoadingPreview(true);
    try {
      const { data } = await api.get("/admin/digest/preview", { params: { frequency: cfg.frequency, full: false } });
      setPreview(data.html);
    } catch (e) { toast.error("Preview failed"); } finally { setLoadingPreview(false); }
  };

  if (!cfg) return null;
  const sel = "neu-input rounded-2xl py-3 px-4 text-sm";
  const lastSent = cfg.last_sent ? new Date(cfg.last_sent).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Never";
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="digest-card">
      <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Mail className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Scheduled digest email</h3>
            <p className="text-sm text-muted-stitch">Automated summary: new signups, open support requests, top pages and automation health.</p>
          </div>
        </div>
        <button data-testid="digest-enabled-toggle" onClick={() => setCfg({ ...cfg, enabled: !cfg.enabled })}
          className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${cfg.enabled ? "justify-end" : "justify-start"}`}
          style={{ background: cfg.enabled ? "var(--primary)" : "var(--neu-dark)" }}>
          <span className="w-6 h-6 rounded-full bg-white shadow" />
        </button>
      </div>

      <div className="grid sm:grid-cols-3 gap-3 mt-4">
        <div>
          <label className="text-xs font-semibold text-muted-stitch">Frequency</label>
          <select data-testid="digest-frequency" value={cfg.frequency} onChange={(e) => setCfg({ ...cfg, frequency: e.target.value })} className={`${sel} w-full mt-1`}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-semibold text-muted-stitch">
            {cfg.frequency === "weekly" ? "Day of week" : cfg.frequency === "monthly" ? "Day of month" : "Day"}
          </label>
          {cfg.frequency === "weekly" ? (
            <select data-testid="digest-day-week" value={cfg.day_of_week} onChange={(e) => setCfg({ ...cfg, day_of_week: parseInt(e.target.value) })} className={`${sel} w-full mt-1`}>
              {DOW.map((d, i) => <option key={i} value={i}>{d}</option>)}
            </select>
          ) : cfg.frequency === "monthly" ? (
            <select data-testid="digest-day-month" value={cfg.day_of_month} onChange={(e) => setCfg({ ...cfg, day_of_month: parseInt(e.target.value) })} className={`${sel} w-full mt-1`}>
              {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          ) : (
            <select disabled className={`${sel} w-full mt-1 opacity-50`}><option>Every day</option></select>
          )}
        </div>
        <div>
          <label className="text-xs font-semibold text-muted-stitch">Time (UTC)</label>
          <select data-testid="digest-hour" value={cfg.hour} onChange={(e) => setCfg({ ...cfg, hour: parseInt(e.target.value) })} className={`${sel} w-full mt-1`}>
            {Array.from({ length: 24 }, (_, i) => i).map((h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}
          </select>
        </div>
      </div>

      <div className="mt-3">
        <label className="text-xs font-semibold text-muted-stitch">Recipient email</label>
        <input data-testid="digest-recipient" value={cfg.recipient} onChange={(e) => setCfg({ ...cfg, recipient: e.target.value })} placeholder="admin@godesk.io" className={`${sel} w-full mt-1`} />
      </div>

      <p data-testid="digest-last-sent" className="text-xs text-muted-stitch mt-3">Last sent: <span className="font-semibold" style={{ color: "var(--text)" }}>{lastSent}</span></p>

      <div className="mt-4 flex items-center gap-3 flex-wrap">
        <button data-testid="save-digest-btn" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold">{saving ? "Saving…" : "Save schedule"}</button>
        <button data-testid="send-digest-now-btn" onClick={sendNow} disabled={sending} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch">{sending ? "Sending…" : "Send now"}</button>
        <button data-testid="send-report-btn" onClick={sendReport} disabled={reporting} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch">{reporting ? "Sending…" : "Send Report"}</button>
        <button data-testid="preview-digest-btn" onClick={togglePreview} disabled={loadingPreview} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-muted-stitch">{loadingPreview ? "Loading…" : preview ? "Hide preview" : "Preview"}</button>
      </div>

      {preview && (
        <iframe data-testid="digest-preview" title="Digest preview" srcDoc={preview}
          className="w-full mt-4 rounded-2xl neu-pressed" style={{ height: 480, border: "none", background: "#f6f6f6" }} />
      )}
      {result && (
        <div data-testid="digest-result" className={`neu-pressed rounded-2xl p-4 mt-4 text-sm ${result.ok ? "text-green-500" : "text-red-400"}`}>
          {result.ok ? "✓ " : "✕ "}{result.detail}
        </div>
      )}

      {history.length > 0 && (
        <div className="mt-5" data-testid="digest-history">
          <p className="text-xs font-semibold text-muted-stitch mb-2">Send history</p>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {history.map((h, i) => (
              <div key={i} data-testid="digest-history-row" className="neu-pressed rounded-2xl px-4 py-2.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>
                    <span className="text-xs uppercase tracking-wide text-muted-stitch mr-2">{h.kind}</span>{h.recipient}
                  </p>
                  <p className="text-xs text-muted-stitch truncate">{new Date(h.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })} · {h.detail}</p>
                </div>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full shrink-0 ${h.ok ? "text-green-500" : "text-red-400"}`} style={{ background: "var(--neu-dark)" }}>
                  {h.ok ? "Sent" : "Failed"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TestEmailCard() {
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const send = async () => {
    setBusy(true); setResult(null);
    try {
      const { data } = await api.post("/admin/test-email", { to: to || undefined });
      setResult(data);
      toast[data.ok ? "success" : "error"](data.ok ? `Sent to ${data.to}` : "Send failed");
    } catch (e) { toast.error("Request failed"); } finally { setBusy(false); }
  };
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="test-email-card">
      <div className="flex items-center gap-3 mb-1">
        <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Mail className="w-5 h-5 text-primary-stitch" /></div>
        <div>
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Test email delivery</h3>
          <p className="text-sm text-muted-stitch">Send a test message to confirm Resend/SMTP is working. Leave blank to send to yourself.</p>
        </div>
      </div>
      <div className="flex gap-3 mt-4 flex-wrap">
        <input data-testid="test-email-input" value={to} onChange={(e) => setTo(e.target.value)} placeholder="you@example.com (optional)" className="neu-input flex-1 min-w-[14rem] rounded-2xl py-3 px-4 text-sm" />
        <button data-testid="send-test-email-btn" onClick={send} disabled={busy} className="neu-primary rounded-2xl px-6 py-3 font-semibold">{busy ? "Sending…" : "Send test"}</button>
      </div>
      {result && (
        <div data-testid="test-email-result" className={`neu-pressed rounded-2xl p-4 mt-4 text-sm ${result.ok ? "text-green-500" : "text-red-400"}`}>
          {result.ok ? "✓ " : "✕ "}{result.detail}
        </div>
      )}
    </div>
  );
}

function AutomationTab() {
  const [data, setData] = useState(null);
  const [runs, setRuns] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [filter, setFilter] = useState("all"); // all | ok | fail | run | mcp_call
  const [alerts, setAlerts] = useState(null);
  const [savingAlerts, setSavingAlerts] = useState(false);
  const PAGE = 20;

  const fetchPage = (skip, append) => {
    const params = { limit: PAGE, skip };
    if (filter === "ok") params.ok = "true";
    else if (filter === "fail") params.ok = "false";
    else if (filter === "run" || filter === "mcp_call") params.kind = filter;
    return api.get("/admin/integration-runs", { params }).then(({ data }) => {
      setData(data);
      setHasMore(data.has_more);
      setRuns((prev) => (append ? [...prev, ...data.runs] : data.runs));
    }).catch(() => { setData({ total: 0, ok_count: 0, fail_count: 0 }); setRuns([]); setHasMore(false); });
  };
  const load = () => fetchPage(0, false);
  const loadMore = () => fetchPage(runs.length, true);
  useEffect(() => { load(); }, [filter]); // eslint-disable-line
  useEffect(() => { api.get("/admin/automation-alerts").then(({ data }) => setAlerts(data)).catch(() => setAlerts({ enabled: false, threshold: 3, email: "", webhook_url: "" })); }, []);

  const saveAlerts = async () => {
    setSavingAlerts(true);
    try {
      await api.put("/admin/automation-alerts", alerts);
      toast.success(alerts.enabled ? "Failure alerts enabled" : "Alert settings saved");
    } catch (e) { toast.error("Save failed"); } finally { setSavingAlerts(false); }
  };

  if (!data) return <Loader />;
  const FILTERS = [["all", "All"], ["ok", "Succeeded"], ["fail", "Failed"], ["run", "N8N runs"], ["mcp_call", "MCP calls"]];
  return (
    <div className="space-y-6" data-testid="automation-tab">
      <div className="grid grid-cols-3 gap-5">
        <StatCard label="Total runs" value={data.total} />
        <StatCard label="Succeeded" value={data.ok_count} color="#16a34a" />
        <StatCard label="Failed" value={data.fail_count} color="#dc2626" />
      </div>

      {alerts && (
        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="automation-alerts-card">
          <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
            <div>
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Failure alerts</h3>
              <p className="text-sm text-muted-stitch">Get notified when an integration fails repeatedly in a row (in-app, plus optional email & webhook).</p>
            </div>
            <button data-testid="alerts-enabled-toggle" aria-pressed={alerts.enabled} onClick={() => setAlerts({ ...alerts, enabled: !alerts.enabled })}
              className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${alerts.enabled ? "justify-end" : "justify-start"}`}
              style={{ background: alerts.enabled ? "var(--primary)" : "var(--neu-dark)" }}>
              <span className="w-6 h-6 rounded-full bg-white shadow" />
            </button>
          </div>
          <div className="grid sm:grid-cols-3 gap-3 mt-4">
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Failures in a row</label>
              <input data-testid="alerts-threshold-input" type="number" min="1" max="20" value={alerts.threshold}
                onChange={(e) => setAlerts({ ...alerts, threshold: e.target.value })} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Alert email (optional)</label>
              <input data-testid="alerts-email-input" value={alerts.email}
                onChange={(e) => setAlerts({ ...alerts, email: e.target.value })} placeholder="ops@yourco.com" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Webhook URL (optional)</label>
              <input data-testid="alerts-webhook-input" value={alerts.webhook_url}
                onChange={(e) => setAlerts({ ...alerts, webhook_url: e.target.value })} placeholder="https://hooks.slack.com/…" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 font-mono-stitch" />
            </div>
          </div>
          <button data-testid="save-alerts-btn" onClick={saveAlerts} disabled={savingAlerts} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingAlerts ? "Saving…" : "Save alert settings"}</button>
          <p className="text-xs text-muted-stitch mt-3">Email uses the platform SMTP (Admin → Meetings). Webhook receives a JSON POST with the integration name, type and failure count.</p>
        </div>
      )}

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Automation activity</h3>
            <p className="text-sm text-muted-stitch">Every N8N workflow trigger and MCP tool call across the platform.</p>
          </div>
          <button data-testid="automation-refresh" onClick={load} className="neu-btn rounded-xl px-4 py-2 text-sm font-semibold text-primary-stitch">Refresh</button>
        </div>
        <div className="neu-pressed rounded-full p-1.5 flex gap-1 mb-5 overflow-x-auto">
          {FILTERS.map(([id, lbl]) => (
            <button key={id} data-testid={`automation-filter-${id}`} onClick={() => setFilter(id)}
              className={`rounded-full py-2 px-4 text-sm font-semibold whitespace-nowrap ${filter === id ? "neu-primary" : "text-muted-stitch"}`}>{lbl}</button>
          ))}
        </div>
        {runs.length === 0 ? (
          <p className="text-sm text-muted-stitch" data-testid="automation-empty">No automation runs recorded yet.</p>
        ) : (
          <>
            <div className="space-y-3">
              {runs.map((r) => (
                <div key={r.run_id} data-testid="automation-run-row" className="neu-pressed rounded-2xl p-4 flex items-center gap-4">
                  <span className={`w-2.5 h-2.5 rounded-full shrink-0`} style={{ background: r.ok ? "#16a34a" : "#dc2626" }} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>
                      {r.integration_name} <span className="text-muted-stitch font-normal">· {r.kind === "mcp_call" ? "MCP tool" : "N8N run"}</span>
                      {r.status_code ? <span className="text-muted-stitch font-normal"> · {r.status_code}</span> : null}
                    </p>
                    <p className="text-xs text-muted-stitch truncate">{r.owner_name} · {new Date(r.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
                  </div>
                  <span className={`text-xs px-3 py-1 rounded-full neu-sm font-semibold ${r.ok ? "text-green-500" : "text-red-500"}`}>{r.ok ? "OK" : "Failed"}</span>
                </div>
              ))}
            </div>
            {hasMore && (
              <button data-testid="automation-load-more" onClick={loadMore} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch mt-5 w-full">Load more</button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div className="neu-raised rounded-[1.5rem] p-6 animate-fade-up">
      <p className="font-head font-black text-4xl" style={{ color: color || "var(--text)" }}>{value}</p>
      <p className="text-sm text-muted-stitch mt-1">{label}</p>
    </div>
  );
}


function MeetingsTab() {
  const navigate = useNavigate();
  const [items, setItems] = useState(null);
  const [creating, setCreating] = useState(false);
  const [turn, setTurn] = useState(null);
  const [savingTurn, setSavingTurn] = useState(false);
  const [sfu, setSfu] = useState(null);
  const [savingSfu, setSavingSfu] = useState(false);
  const [smtp, setSmtp] = useState(null);
  const [savingSmtp, setSavingSmtp] = useState(false);
  const load = () => api.get("/admin/meetings").then(({ data }) => setItems(data)).catch(() => setItems([]));
  useEffect(() => {
    load(); const t = setInterval(load, 10000);
    api.get("/admin/rtc-config").then(({ data }) => setTurn(data)).catch(() => setTurn({ urls: "", username: "", has_credential: false }));
    api.get("/admin/sfu-config").then(({ data }) => setSfu(data)).catch(() => setSfu({ enabled: false, url: "", api_key: "", has_secret: false }));
    api.get("/admin/smtp-config").then(({ data }) => setSmtp(data)).catch(() => setSmtp({ enabled: false, host: "", port: 587, username: "", from_address: "", has_password: false }));
    return () => clearInterval(t);
  }, []);

  const start = async () => {
    setCreating(true);
    try {
      const { data } = await api.post("/meetings", {});
      window.open(`/call/${data.room_id}`, "_blank", "width=1200,height=820");
      toast.success("Meeting started");
      load();
    } catch (e) { toast.error("Could not start meeting"); } finally { setCreating(false); }
  };
  const end = async (roomId) => {
    try { await api.post(`/admin/meetings/${roomId}/end`); toast.success("Meeting ended"); load(); }
    catch (e) { toast.error("Failed to end meeting"); }
  };
  const saveTurn = async () => {
    setSavingTurn(true);
    try {
      await api.put("/admin/rtc-config", { urls: turn.urls, username: turn.username, credential: turn.credential || "" });
      toast.success("TURN server saved — calls will use it for reliable connectivity");
      const { data } = await api.get("/admin/rtc-config"); setTurn(data);
    } catch (e) { toast.error("Save failed"); } finally { setSavingTurn(false); }
  };
  const saveSfu = async () => {
    setSavingSfu(true);
    try {
      await api.put("/admin/sfu-config", { enabled: sfu.enabled, url: sfu.url, api_key: sfu.api_key, api_secret: sfu.api_secret || "" });
      toast.success(sfu.enabled ? "SFU enabled — new calls will route through LiveKit" : "SFU settings saved");
      const { data } = await api.get("/admin/sfu-config"); setSfu(data);
    } catch (e) { toast.error("Save failed"); } finally { setSavingSfu(false); }
  };
  const saveSmtp = async () => {
    setSavingSmtp(true);
    try {
      await api.put("/admin/smtp-config", { enabled: smtp.enabled, host: smtp.host, port: smtp.port, username: smtp.username, from_address: smtp.from_address, password: smtp.password || "" });
      toast.success(smtp.enabled ? "Email enabled — meeting invites will be sent" : "Email settings saved");
      const { data } = await api.get("/admin/smtp-config"); setSmtp(data);
    } catch (e) { toast.error("Save failed"); } finally { setSavingSmtp(false); }
  };
  const clearTurn = async () => {
    try { await api.delete("/admin/rtc-config"); const { data } = await api.get("/admin/rtc-config"); setTurn(data); toast.success("TURN credentials cleared"); }
    catch (e) { toast.error("Failed to clear"); }
  };
  const clearSfu = async () => {
    try { await api.delete("/admin/sfu-config"); const { data } = await api.get("/admin/sfu-config"); setSfu(data); toast.success("SFU credentials cleared"); }
    catch (e) { toast.error("Failed to clear"); }
  };
  const clearSmtp = async () => {
    try { await api.delete("/admin/smtp-config"); const { data } = await api.get("/admin/smtp-config"); setSmtp(data); toast.success("Email credentials cleared"); }
    catch (e) { toast.error("Failed to clear"); }
  };

  if (!items || !turn || !sfu || !smtp) return <Loader />;
  return (
    <div className="space-y-6">
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up flex items-center justify-between gap-4 flex-wrap" data-testid="admin-meetings-card">
        <div>
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Meetings</h3>
          <p className="text-sm text-muted-stitch">Start a call or monitor and end active meetings across the platform.</p>
        </div>
        <button data-testid="admin-start-meeting" onClick={start} disabled={creating} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2">
          <Plus className="w-5 h-5" /> {creating ? "Starting…" : "New meeting"}
        </button>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="turn-config-card">
        <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>Call quality — TURN server</h3>
        <p className="text-sm text-muted-stitch mb-4">Calls use free STUN by default. For rock-solid connectivity behind strict firewalls, run your own <span className="font-mono-stitch">coturn</span> server and enter its details here (no third party required). Applies to all calls instantly.</p>
        <div className="grid sm:grid-cols-3 gap-3">
          <input data-testid="turn-urls-input" value={turn.urls} onChange={(e) => setTurn({ ...turn, urls: e.target.value })} placeholder="turn:your-host:3478" className="neu-input rounded-2xl py-3 px-4 font-mono-stitch text-sm" />
          <input data-testid="turn-username-input" value={turn.username} onChange={(e) => setTurn({ ...turn, username: e.target.value })} placeholder="username" className="neu-input rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="turn-credential-input" type="password" value={turn.credential || ""} onChange={(e) => setTurn({ ...turn, credential: e.target.value })} placeholder={turn.has_credential ? "•••••• (saved)" : "credential"} className="neu-input rounded-2xl py-3 px-4 text-sm" />
        </div>
        <button data-testid="save-turn-btn" onClick={saveTurn} disabled={savingTurn} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingTurn ? "Saving…" : "Save TURN server"}</button>
        <button data-testid="clear-turn-btn" onClick={clearTurn} className="neu-btn rounded-2xl px-6 py-3 font-semibold mt-4 ml-3 text-red-500">Clear credentials</button>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="sfu-config-card">
        <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Large group calls — self-hosted SFU (LiveKit)</h3>
          <button data-testid="sfu-enabled-toggle" onClick={() => setSfu({ ...sfu, enabled: !sfu.enabled })}
            className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${sfu.enabled ? "justify-end" : "justify-start"}`}
            style={{ background: sfu.enabled ? "var(--primary)" : "var(--neu-dark)" }}>
            <span className="w-6 h-6 rounded-full bg-white shadow" />
          </button>
        </div>
        <p className="text-sm text-muted-stitch mb-4">For big meetings, route calls through your own <span className="font-mono-stitch">LiveKit</span> media server instead of peer-to-peer. Requires a deployed LiveKit server with open UDP ports — leave OFF to use the built-in P2P calls (default).</p>
        <div className="grid sm:grid-cols-3 gap-3">
          <input data-testid="sfu-url-input" value={sfu.url} onChange={(e) => setSfu({ ...sfu, url: e.target.value })} placeholder="wss://livekit.your-host.com" className="neu-input rounded-2xl py-3 px-4 font-mono-stitch text-sm" />
          <input data-testid="sfu-key-input" value={sfu.api_key} onChange={(e) => setSfu({ ...sfu, api_key: e.target.value })} placeholder="API key" className="neu-input rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="sfu-secret-input" type="password" value={sfu.api_secret || ""} onChange={(e) => setSfu({ ...sfu, api_secret: e.target.value })} placeholder={sfu.has_secret ? "•••••• (saved)" : "API secret"} className="neu-input rounded-2xl py-3 px-4 text-sm" />
        </div>
        <button data-testid="save-sfu-btn" onClick={saveSfu} disabled={savingSfu} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingSfu ? "Saving…" : "Save SFU settings"}</button>
        <button data-testid="clear-sfu-btn" onClick={clearSfu} className="neu-btn rounded-2xl px-6 py-3 font-semibold mt-4 ml-3 text-red-500">Clear credentials</button>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="smtp-config-card">
        <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Email (SMTP) — meeting invites</h3>
          <button data-testid="smtp-enabled-toggle" onClick={() => setSmtp({ ...smtp, enabled: !smtp.enabled })}
            className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${smtp.enabled ? "justify-end" : "justify-start"}`}
            style={{ background: smtp.enabled ? "var(--primary)" : "var(--neu-dark)" }}>
            <span className="w-6 h-6 rounded-full bg-white shadow" />
          </button>
        </div>
        <p className="text-sm text-muted-stitch mb-4">Connect any SMTP account (Gmail app password, Outlook, or your own mail server) to email meeting invites with calendar links. No third-party service required.</p>
        <div className="grid sm:grid-cols-2 gap-3">
          <input data-testid="smtp-host-input" value={smtp.host} onChange={(e) => setSmtp({ ...smtp, host: e.target.value })} placeholder="smtp.gmail.com" className="neu-input rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="smtp-port-input" type="number" value={smtp.port} onChange={(e) => setSmtp({ ...smtp, port: e.target.value })} placeholder="587" className="neu-input rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="smtp-username-input" value={smtp.username} onChange={(e) => setSmtp({ ...smtp, username: e.target.value })} placeholder="you@gmail.com" className="neu-input rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="smtp-password-input" type="password" value={smtp.password || ""} onChange={(e) => setSmtp({ ...smtp, password: e.target.value })} placeholder={smtp.has_password ? "•••••• (saved)" : "app password"} className="neu-input rounded-2xl py-3 px-4 text-sm" />
          <input data-testid="smtp-from-input" value={smtp.from_address} onChange={(e) => setSmtp({ ...smtp, from_address: e.target.value })} placeholder="from address (e.g. you@gmail.com)" className="neu-input rounded-2xl py-3 px-4 text-sm sm:col-span-2" />
        </div>
        <button data-testid="save-smtp-btn" onClick={saveSmtp} disabled={savingSmtp} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingSmtp ? "Saving…" : "Save email settings"}</button>
        <button data-testid="clear-smtp-btn" onClick={clearSmtp} className="neu-btn rounded-2xl px-6 py-3 font-semibold mt-4 ml-3 text-red-500">Clear credentials</button>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        {items.length === 0 ? (
          <p className="text-sm text-muted-stitch">No meetings yet.</p>
        ) : (
          <div className="space-y-3">
            {items.map((m) => (
              <div key={m.room_id} data-testid="admin-meeting-row" className="neu-pressed rounded-2xl p-4 flex items-center gap-4">
                <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0"><Video className="w-5 h-5 text-primary-stitch" /></div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold truncate flex items-center gap-2" style={{ color: "var(--text)" }}>
                    {m.name}
                    {m.live && <span className="text-[11px] font-bold px-2 py-0.5 rounded-full text-white flex items-center gap-1" style={{ background: "#16a34a" }}><UsersIcon className="w-3 h-3" /> {m.participants} live</span>}
                  </p>
                  <p className="text-xs text-muted-stitch truncate">{m.room_id} · host {m.host_name}</p>
                </div>
                <button onClick={() => navigate(`/call/${m.room_id}`)} className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold text-primary-stitch">Join</button>
                {m.live && (
                  <button data-testid="admin-end-meeting" onClick={() => end(m.room_id)} className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold text-red-500 flex items-center gap-1.5">
                    <PhoneOff className="w-4 h-4" /> End
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
