import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard, MessagesSquare, FolderKanban, FolderOpen, Plug,
  Sparkles, User, Settings, Shield, LogOut, Menu, Sun, Moon, Users, Eye,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { FeaturesProvider, useFeatures } from "@/context/FeaturesContext";
import NotificationBell from "@/components/NotificationBell";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, flag: null },
  { to: "/messages", label: "Messages", icon: MessagesSquare, flag: "chat" },
  { to: "/projects", label: "Projects", icon: FolderKanban, flag: "projects" },
  { to: "/assets", label: "Assets", icon: FolderOpen, flag: "assets" },
  { to: "/integrations", label: "Integrations", icon: Plug, flag: "integrations" },
  { to: "/assistant", label: "AI Assistant", icon: Sparkles, flag: "ai_assistant" },
  { to: "/people", label: "People", icon: Users, flag: "friends" },
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
  const { user, logout, impersonating, stopImpersonation } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { flags } = useFeatures();
  const navigate = useNavigate();

  const doLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const initials = (user?.name || user?.email || "U").slice(0, 1).toUpperCase();

  return (
    <div className="stitch-wallpaper min-h-screen flex">
      <motion.aside
        animate={{ width: collapsed ? 88 : 280 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        className="neu-raised m-4 rounded-[1.75rem] flex flex-col overflow-hidden relative z-10"
        style={{ height: "calc(100vh - 2rem)" }}
        data-testid="sidebar"
      >
        <div className="flex items-center gap-3 p-5">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0">
            <span className="font-head font-black text-xl text-primary-stitch">S</span>
          </div>
          {!collapsed && <span className="font-head font-black text-2xl tracking-tight" style={{ color: "var(--text)" }}>Stitches</span>}
        </div>

        <button
          data-testid="sidebar-toggle-button"
          onClick={() => setCollapsed((c) => !c)}
          className="neu-btn mx-5 mb-4 rounded-xl py-2 flex items-center justify-center text-muted-stitch"
        >
          <Menu className="w-5 h-5" />
        </button>

        <nav className="flex-1 px-4 space-y-2 overflow-y-auto">
          {NAV.filter((n) => !n.flag || flags[n.flag]).map(({ to, label, icon: Icon }) => (
            <SideLink key={to} to={to} label={label} Icon={Icon} collapsed={collapsed} />
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
      </motion.aside>

      <main className="flex-1 min-w-0 relative z-10 flex flex-col" style={{ height: "100vh" }}>
        {impersonating && (
          <div data-testid="impersonation-banner" className="flex items-center justify-between gap-3 px-6 py-2.5 text-sm font-semibold text-white shrink-0" style={{ background: "var(--primary)" }}>
            <span className="flex items-center gap-2"><Eye className="w-4 h-4" /> Viewing as {user?.name} ({user?.email})</span>
            <button data-testid="return-admin-btn" onClick={async () => { await stopImpersonation(); navigate("/admin"); }} className="rounded-full px-4 py-1 bg-white/20 hover:bg-white/30 transition-colors">
              Return to admin
            </button>
          </div>
        )}
        <div className="flex items-center justify-end gap-3 px-6 pt-5 shrink-0">
          <NotificationBell />
        </div>
        <div className="flex-1 overflow-y-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function SideLink({ to, label, Icon, collapsed, testid }) {
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
      <Icon className="w-5 h-5 shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  );
}
