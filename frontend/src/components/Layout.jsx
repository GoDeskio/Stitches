import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard, MessagesSquare, FolderKanban, FolderOpen, Plug,
  Sparkles, User, Settings, Shield, LogOut, Menu, X, Sun, Moon, Users, Eye, StickyNote,
  Activity, Download, Video, MailWarning, Lock, Bot,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { FeaturesProvider, useFeatures } from "@/context/FeaturesContext";
import NotificationBell from "@/components/NotificationBell";
import InstallPrompt from "@/components/InstallPrompt";
import { toast } from "sonner";
import api from "@/lib/api";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, flag: null },
  { to: "/messages", label: "Messages", icon: MessagesSquare, flag: "chat" },
  { to: "/projects", label: "Projects", icon: FolderKanban, flag: "projects" },
  { to: "/assets", label: "Assets", icon: FolderOpen, flag: "assets" },
  { to: "/integrations", label: "Integrations", icon: Plug, flag: "integrations" },
  { to: "/bots", label: "Bots", icon: Bot, flag: null },
  { to: "/assistant", label: "AI Assistant", icon: Sparkles, flag: "ai_assistant" },
  { to: "/meetings", label: "Meetings", icon: Video, flag: null },
  { to: "/notes", label: "Notes", icon: StickyNote, flag: null },
  { to: "/people", label: "People", icon: Users, flag: "friends" },
  { to: "/activity", label: "Activity", icon: Activity, flag: null },
  { to: "/downloads", label: "Downloads", icon: Download, flag: null },
];

export default function Layout() {
  return (
    <FeaturesProvider>
      <LayoutInner />
    </FeaturesProvider>
  );
}

function LayoutInner() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout, impersonating, stopImpersonation } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { flags, entitled, entitlements } = useFeatures();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  useEffect(() => {
    const ping = () => api.post("/presence/ping").catch(() => {});
    ping();
    const t = setInterval(ping, 30000);
    return () => clearInterval(t);
  }, []);

  const [unreadTotal, setUnreadTotal] = useState(0);
  useEffect(() => {
    const load = () => api.get("/unreads").then(({ data }) => setUnreadTotal(data.total)).catch(() => {});
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const doLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const initials = (user?.name || user?.email || "U").slice(0, 1).toUpperCase();

  return (
    <div className="stitch-wallpaper min-h-screen flex">
      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 inset-x-0 z-30 h-14 neu-raised flex items-center justify-between px-4" style={{ borderRadius: 0 }} data-testid="mobile-topbar">
        <button data-testid="mobile-menu-button" onClick={() => setMobileOpen(true)} className="neu-btn rounded-xl p-2 text-muted-stitch">
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <img src="/logo.png" alt="Stitches" className="w-8 h-8 object-contain" />
          <span className="font-head font-black text-lg tracking-tight" style={{ color: "var(--text)" }}>Stitches</span>
        </div>
        <NotificationBell />
      </div>

      {/* Mobile backdrop */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 bg-black/60 z-40" onClick={() => setMobileOpen(false)} data-testid="mobile-backdrop" />
      )}

      <aside
        className={`neu-raised m-4 rounded-[1.75rem] flex flex-col overflow-hidden fixed md:relative z-50 md:z-10 top-0 left-0 transition-transform duration-300 ${mobileOpen ? "translate-x-0" : "-translate-x-[120%]"} md:translate-x-0`}
        style={{ height: "calc(100vh - 2rem)", width: collapsed ? 88 : 280, transition: "transform 0.3s ease, width 0.3s ease" }}
        data-testid="sidebar"
      >
        <div className="flex items-center gap-3 p-5">
          <img src="/logo.png" alt="Stitches" className="w-11 h-11 object-contain shrink-0" />
          {!collapsed && <span className="font-head font-black text-2xl tracking-tight" style={{ color: "var(--text)" }}>Stitches</span>}
        </div>

        <button
          data-testid="sidebar-toggle-button"
          onClick={() => setCollapsed((c) => !c)}
          className="hidden md:flex neu-btn mx-5 mb-4 rounded-xl py-2 items-center justify-center text-muted-stitch"
        >
          <Menu className="w-5 h-5" />
        </button>
        <button
          data-testid="mobile-close-button"
          onClick={() => setMobileOpen(false)}
          className="md:hidden neu-btn mx-5 mb-4 rounded-xl py-2 flex items-center justify-center gap-2 text-muted-stitch"
        >
          <X className="w-5 h-5" /> <span className="text-sm font-medium">Close</span>
        </button>

        <nav className="flex-1 px-4 space-y-2 overflow-y-auto">
          {NAV.filter((n) => !n.flag || flags[n.flag]).map(({ to, label, icon: Icon, flag }) => (
            <SideLink key={to} to={to} label={label} Icon={Icon} collapsed={collapsed}
              badge={to === "/messages" ? unreadTotal : 0} locked={flag ? !entitled(flag) : false} />
          ))}
          {user?.role === "admin" && (
            <SideLink to="/admin" label="Admin" Icon={Shield} collapsed={collapsed} testid="nav-admin" />
          )}
        </nav>

        <div className="p-4 space-y-2">
          <SideLink to="/profile" label="Profile" Icon={User} collapsed={collapsed} />
          <SideLink to="/settings" label="Settings" Icon={Settings} collapsed={collapsed} />
          <button onClick={toggleTheme} data-testid="theme-toggle"
            className="neu-btn w-full rounded-xl py-2.5 flex items-center gap-3 px-3 text-muted-stitch">
            {theme === "dark" ? <Sun className="w-5 h-5 shrink-0" /> : <Moon className="w-5 h-5 shrink-0" />}
            {!collapsed && <span className="text-sm font-medium">{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>}
          </button>

          {entitlements.gating && !entitlements.all_access && (
            <button onClick={() => navigate("/pricing")} data-testid="sidebar-upgrade"
              className="neu-btn w-full rounded-xl py-2.5 flex items-center gap-3 px-3 text-primary-stitch">
              <Sparkles className="w-5 h-5 shrink-0" />
              {!collapsed && <span className="text-sm font-semibold truncate">Upgrade{entitlements.plan_name ? ` · ${entitlements.plan_name}` : ""}</span>}
            </button>
          )}

          <div className="neu-pressed rounded-2xl p-3 flex items-center gap-3 mt-3">
            <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center shrink-0 overflow-hidden">
              {user?.avatar ? <img src={user.avatar} alt="" className="w-full h-full object-cover" /> :
                <span className="font-head font-bold text-primary-stitch">{initials}</span>}
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{user?.name}</p>
                <p className="text-xs truncate text-muted-stitch">{user?.email}</p>
              </div>
            )}
            {!collapsed && (
              <button onClick={doLogout} data-testid="logout-btn" className="text-muted-stitch hover:text-primary-stitch transition-colors">
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 relative z-10 flex flex-col pt-14 md:pt-0" style={{ height: "100vh" }}>
        {impersonating && (
          <div data-testid="impersonation-banner" className="flex items-center justify-between gap-3 px-6 py-2.5 text-sm font-semibold text-white shrink-0" style={{ background: "var(--primary)" }}>
            <span className="flex items-center gap-2"><Eye className="w-4 h-4" /> Viewing as {user?.name} ({user?.email})</span>
            <button data-testid="return-admin-btn" onClick={async () => { await stopImpersonation(); navigate("/admin"); }} className="rounded-full px-4 py-1 bg-white/20 hover:bg-white/30 transition-colors">
              Return to admin
            </button>
          </div>
        )}
        <div className="hidden md:flex items-center justify-end gap-3 px-6 pt-5 shrink-0">
          <NotificationBell />
        </div>
        <div className="flex-1 overflow-y-auto">
          <VerifyBanner />
          <Outlet />
        </div>
      </main>
      <InstallPrompt />
    </div>
  );
}

function VerifyBanner() {
  const { user } = useAuth();
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  if (!user || user.email_verified !== false) return null;
  const resend = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/auth/resend-verification");
      setSent(true);
      (data.ok ? toast.success : toast.error)(data.message);
    } catch (e) { toast.error("Could not send verification email"); } finally { setSending(false); }
  };
  return (
    <div data-testid="verify-email-banner" className="flex items-center justify-between gap-3 px-6 py-3 mx-4 mt-4 rounded-2xl text-sm neu-pressed" style={{ borderLeft: "3px solid var(--primary)" }}>
      <span className="flex items-center gap-2" style={{ color: "var(--text)" }}>
        <MailWarning className="w-4 h-4 text-primary-stitch shrink-0" />
        Please verify your email <span className="font-semibold">{user.email}</span> to secure your account.
      </span>
      <button data-testid="resend-verification-btn" onClick={resend} disabled={sending || sent}
        className="neu-btn rounded-xl px-4 py-2 text-sm font-semibold text-primary-stitch shrink-0">
        {sent ? "Email sent ✓" : sending ? "Sending…" : "Resend email"}
      </button>
    </div>
  );
}

function SideLink({ to, label, Icon, collapsed, testid, badge = 0, locked = false }) {
  const navigate = useNavigate();
  if (locked) {
    return (
      <button
        onClick={() => navigate("/pricing")}
        data-testid={`nav-locked-${label.toLowerCase().replace(/\s/g, "-")}`}
        title={`Upgrade to unlock ${label}`}
        className="w-full rounded-xl py-2.5 px-3 flex items-center gap-3 font-medium text-sm transition-all text-muted-stitch neu-hover opacity-60"
      >
        <span className="relative shrink-0"><Icon className="w-5 h-5" /></span>
        {!collapsed && <span className="truncate flex-1 text-left">{label}</span>}
        {!collapsed && <Lock className="w-3.5 h-3.5 shrink-0" />}
      </button>
    );
  }
  return (
    <NavLink
      to={to}
      data-testid={testid || `nav-${label.toLowerCase().replace(/\s/g, "-")}`}
      className={({ isActive }) =>
        `w-full rounded-xl py-2.5 px-3 flex items-center gap-3 font-medium text-sm transition-all ${
          isActive ? "neu-pressed text-primary-stitch" : "text-muted-stitch neu-hover"
        }`
      }
    >
      <span className="relative shrink-0">
        <Icon className="w-5 h-5" />
        {collapsed && badge > 0 && <span className="absolute -top-1.5 -right-1.5 w-2.5 h-2.5 rounded-full" style={{ background: "var(--primary)" }} />}
      </span>
      {!collapsed && <span className="truncate flex-1">{label}</span>}
      {!collapsed && badge > 0 && (
        <span data-testid="nav-messages-badge" className="min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-bold flex items-center justify-center text-white" style={{ background: "var(--primary)" }}>{badge}</span>
      )}
    </NavLink>
  );
}
