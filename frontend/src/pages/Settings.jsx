import { useState } from "react";
import { Save, Sun, Moon, Minus, Plus, User, Building2, FolderKanban, Palette, Bell } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { PageShell, PageHeader } from "@/components/Stitch";

export default function Settings() {
  const { user, updateUser } = useAuth();
  const { theme, setTheme, scale, setScale } = useTheme();
  const [form, setForm] = useState({
    name: user?.name || "", username: user?.username || "", phone: user?.phone || "",
    address: user?.address || "", company: user?.company || "", company_role: user?.company_role || "",
    bio: user?.bio || "", project_info: user?.project_info || "", avatar: user?.avatar || "",
  });
  const [saving, setSaving] = useState(false);
  const [notif, setNotif] = useState({ master: true, workspace: true, project: true, friend: true, ...(user?.notification_prefs || {}) });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggleNotif = (k) => setNotif((n) => ({ ...n, [k]: !n[k] }));

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/users/me", { ...form, theme, ui_scale: scale, notification_prefs: notif });
      updateUser(data);
      toast.success("Settings saved");
    } catch (e) { toast.error("Failed to save"); } finally { setSaving(false); }
  };

  return (
    <PageShell>
      <PageHeader title="Settings" subtitle="Manage your personal information, company details and appearance."
        action={<button data-testid="save-settings-btn" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Save className="w-4 h-4" /> {saving ? "Saving..." : "Save"}</button>} />

      <div className="grid lg:grid-cols-2 gap-6">
        <Section icon={User} title="Personal Information">
          <Input label="Full name" value={form.name} onChange={set("name")} testid="set-name" />
          <Input label="Username" value={form.username} onChange={set("username")} testid="set-username" />
          <Input label="Email" value={user?.email} disabled />
          <Input label="Phone number" value={form.phone} onChange={set("phone")} testid="set-phone" />
          <Input label="Address" value={form.address} onChange={set("address")} testid="set-address" />
          <Input label="Avatar URL" value={form.avatar} onChange={set("avatar")} testid="set-avatar" />
          <Textarea label="Bio" value={form.bio} onChange={set("bio")} />
        </Section>

        <div className="space-y-6">
          <Section icon={Building2} title="Company">
            <Input label="Company name" value={form.company} onChange={set("company")} testid="set-company" />
            <Input label="Your role" value={form.company_role} onChange={set("company_role")} testid="set-role" />
          </Section>

          <Section icon={FolderKanban} title="Project Information">
            <Textarea label="What are you working on?" value={form.project_info} onChange={set("project_info")} testid="set-project-info" />
          </Section>

          <Section icon={Palette} title="Appearance">
            <div>
              <label className="text-sm font-semibold text-muted-stitch">Theme</label>
              <div className="neu-pressed rounded-full p-1.5 flex mt-2">
                <button data-testid="set-theme-light" onClick={() => setTheme("light")} className={`flex-1 rounded-full py-2.5 text-sm font-semibold flex items-center justify-center gap-2 ${theme === "light" ? "neu-primary" : "text-muted-stitch"}`}><Sun className="w-4 h-4" /> Light</button>
                <button data-testid="set-theme-dark" onClick={() => setTheme("dark")} className={`flex-1 rounded-full py-2.5 text-sm font-semibold flex items-center justify-center gap-2 ${theme === "dark" ? "neu-primary" : "text-muted-stitch"}`}><Moon className="w-4 h-4" /> Dark</button>
              </div>
            </div>
            <div className="mt-5">
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-semibold text-muted-stitch">Interface size</label>
                <span className="text-sm font-mono-stitch text-primary-stitch">{Math.round(scale * 100)}%</span>
              </div>
              <div className="flex items-center gap-3">
                <button data-testid="scale-down" onClick={() => setScale(Math.max(0.8, +(scale - 0.1).toFixed(2)))} className="neu-btn w-11 h-11 rounded-xl flex items-center justify-center text-primary-stitch"><Minus className="w-5 h-5" /></button>
                <input data-testid="scale-slider" type="range" min="0.8" max="1.3" step="0.05" value={scale} onChange={(e) => setScale(parseFloat(e.target.value))} className="flex-1 accent-current text-primary-stitch" style={{ accentColor: "var(--primary)" }} />
                <button data-testid="scale-up" onClick={() => setScale(Math.min(1.3, +(scale + 0.1).toFixed(2)))} className="neu-btn w-11 h-11 rounded-xl flex items-center justify-center text-primary-stitch"><Plus className="w-5 h-5" /></button>
              </div>
            </div>
          </Section>

          <Section icon={Bell} title="Notifications">
            <NotifToggle label="Enable all notifications" checked={notif.master} onToggle={() => toggleNotif("master")} testid="notif-master" />
            <NotifToggle label="Workspace invites" checked={notif.workspace} onToggle={() => toggleNotif("workspace")} testid="notif-workspace" disabled={!notif.master} />
            <NotifToggle label="Project invites" checked={notif.project} onToggle={() => toggleNotif("project")} testid="notif-project" disabled={!notif.master} />
            <NotifToggle label="New connections" checked={notif.friend} onToggle={() => toggleNotif("friend")} testid="notif-friend" disabled={!notif.master} />
          </Section>
        </div>
      </div>
    </PageShell>
  );
}

function Section({ icon: Icon, title, children }) {
  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up">
      <div className="flex items-center gap-3 mb-6">
        <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Icon className="w-5 h-5 text-primary-stitch" /></div>
        <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{title}</h3>
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Input({ label, value, onChange, disabled, testid }) {
  return (
    <div>
      <label className="text-sm font-semibold text-muted-stitch">{label}</label>
      <input data-testid={testid} value={value || ""} onChange={onChange} disabled={disabled}
        className="neu-input w-full rounded-2xl py-3 px-5 mt-2 disabled:opacity-60" />
    </div>
  );
}

function Textarea({ label, value, onChange, testid }) {
  return (
    <div>
      <label className="text-sm font-semibold text-muted-stitch">{label}</label>
      <textarea data-testid={testid} value={value || ""} onChange={onChange} rows={3}
        className="neu-input w-full rounded-2xl py-3 px-5 mt-2 resize-none" />
    </div>
  );
}

function NotifToggle({ label, checked, onToggle, testid, disabled }) {
  return (
    <div className={`neu-pressed rounded-2xl p-4 flex items-center justify-between ${disabled ? "opacity-50" : ""}`}>
      <span className="font-medium text-sm" style={{ color: "var(--text)" }}>{label}</span>
      <button data-testid={testid} disabled={disabled} onClick={onToggle}
        className={`w-14 h-8 rounded-full flex items-center px-1 transition-all ${checked ? "justify-end" : "justify-start"}`}
        style={{ background: checked ? "var(--primary)" : "var(--neu-dark)" }}>
        <span className="w-6 h-6 rounded-full bg-white shadow" />
      </button>
    </div>
  );
}
