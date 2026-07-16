import { useState, useEffect } from "react";
import { Save, Sun, Moon, Minus, Plus, User, Building2, FolderKanban, Palette, Bell, Upload, Trash2, Smartphone, Monitor, LogOut, ShieldCheck, Mail } from "lucide-react";
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
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [notif, setNotif] = useState({ master: true, workspace: true, project: true, friend: true, security: true, ...(user?.notification_prefs || {}) });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggleNotif = (k) => setNotif((n) => ({ ...n, [k]: !n[k] }));

  const uploadAvatar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingAvatar(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/users/me/avatar", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setForm((f) => ({ ...f, avatar: data.avatar }));
      updateUser({ ...user, avatar: data.avatar });
      toast.success("Profile photo updated");
    } catch (err) { toast.error("Upload failed"); } finally { setUploadingAvatar(false); }
  };

  const removeAvatar = async () => {
    try {
      const { data } = await api.delete("/users/me/avatar");
      setForm((f) => ({ ...f, avatar: "" }));
      updateUser(data);
      toast.success("Profile photo removed");
    } catch (err) { toast.error("Failed to remove photo"); }
  };

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
          <div className="flex items-center gap-4 mb-2">
            <div className="neu-raised w-16 h-16 rounded-2xl flex items-center justify-center overflow-hidden shrink-0">
              {form.avatar ? <img src={form.avatar} alt="" className="w-full h-full object-cover" data-testid="avatar-preview" /> :
                <span className="font-head font-bold text-xl text-primary-stitch">{(form.name || "U")[0].toUpperCase()}</span>}
            </div>
            <div>
              <label data-testid="avatar-upload-label" className="neu-btn rounded-xl px-4 py-2.5 text-sm font-semibold text-primary-stitch cursor-pointer inline-flex items-center gap-2">
                <Upload className="w-4 h-4" /> {uploadingAvatar ? "Uploading…" : "Upload photo"}
                <input data-testid="avatar-file-input" type="file" accept="image/*" className="hidden" onChange={uploadAvatar} disabled={uploadingAvatar} />
              </label>
              {form.avatar && (
                <button data-testid="avatar-remove-btn" onClick={removeAvatar} className="neu-btn rounded-xl px-4 py-2.5 text-sm font-semibold text-muted-stitch inline-flex items-center gap-2 ml-2">
                  <Trash2 className="w-4 h-4" /> Remove
                </button>
              )}
              <p className="text-xs text-muted-stitch mt-1.5">PNG, JPG or WebP. Stored securely.</p>
            </div>
          </div>
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
                <button data-testid="scale-down" onClick={() => setScale(Math.max(0.55, +(scale - 0.05).toFixed(2)))} className="neu-btn w-11 h-11 rounded-xl flex items-center justify-center text-primary-stitch"><Minus className="w-5 h-5" /></button>
                <input data-testid="scale-slider" type="range" min="0.55" max="0.85" step="0.05" value={scale} onChange={(e) => setScale(parseFloat(e.target.value))} className="flex-1 accent-current text-primary-stitch" style={{ accentColor: "var(--primary)" }} />
                <button data-testid="scale-up" onClick={() => setScale(Math.min(0.85, +(scale + 0.05).toFixed(2)))} className="neu-btn w-11 h-11 rounded-xl flex items-center justify-center text-primary-stitch"><Plus className="w-5 h-5" /></button>
              </div>
            </div>
          </Section>

          <Section icon={Bell} title="Notifications">
            <NotifToggle label="Enable all notifications" checked={notif.master} onToggle={() => toggleNotif("master")} testid="notif-master" />
            <NotifToggle label="Workspace invites" checked={notif.workspace} onToggle={() => toggleNotif("workspace")} testid="notif-workspace" disabled={!notif.master} />
            <NotifToggle label="Project invites" checked={notif.project} onToggle={() => toggleNotif("project")} testid="notif-project" disabled={!notif.master} />
            <NotifToggle label="New connections" checked={notif.friend} onToggle={() => toggleNotif("friend")} testid="notif-friend" disabled={!notif.master} />
            <div className="neu-pressed rounded-2xl p-4 flex items-center justify-between border" style={{ borderColor: "var(--primary)" }}>
              <div className="min-w-0 pr-3">
                <span className="font-medium text-sm flex items-center gap-2" style={{ color: "var(--text)" }}><ShieldCheck className="w-4 h-4 text-primary-stitch" /> Security alerts</span>
                <p className="text-xs text-muted-stitch mt-0.5">New sign-in warnings. Delivered even when other notifications are muted.</p>
              </div>
              <button data-testid="notif-security" onClick={() => toggleNotif("security")}
                className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${notif.security ? "justify-end" : "justify-start"}`}
                style={{ background: notif.security ? "var(--primary)" : "var(--neu-dark)" }}>
                <span className="w-6 h-6 rounded-full bg-white shadow" />
              </button>
            </div>
          </Section>
        </div>
      </div>

      <div className="mt-6">
        <DevicesSection />
      </div>

      <div className="mt-6">
        <MySmtpSection />
      </div>
    </PageShell>
  );
}

function MySmtpSection() {
  const [smtp, setSmtp] = useState(null);
  const [saving, setSaving] = useState(false);
  const load = () => api.get("/me/smtp-config").then(({ data }) => setSmtp(data))
    .catch(() => setSmtp({ enabled: false, host: "", port: 587, username: "", from_address: "", has_password: false }));
  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/me/smtp-config", { enabled: smtp.enabled, host: smtp.host, port: smtp.port, username: smtp.username, from_address: smtp.from_address, password: smtp.password || "" });
      toast.success(smtp.enabled ? "Invites will now be sent from your email" : "Email settings saved");
      load();
    } catch (e) { toast.error("Save failed"); } finally { setSaving(false); }
  };
  const clear = async () => {
    try { await api.delete("/me/smtp-config"); toast.success("Your email credentials were cleared"); load(); }
    catch (e) { toast.error("Failed to clear"); }
  };

  if (!smtp) return null;
  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up" data-testid="my-smtp-section">
      <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Mail className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Send invites from your own email</h3>
            <p className="text-sm text-muted-stitch">Optional. When enabled, meeting invites you send use your SMTP account instead of the platform default.</p>
          </div>
        </div>
        <button data-testid="my-smtp-enabled-toggle" onClick={() => setSmtp({ ...smtp, enabled: !smtp.enabled })}
          className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${smtp.enabled ? "justify-end" : "justify-start"}`}
          style={{ background: smtp.enabled ? "var(--primary)" : "var(--neu-dark)" }}>
          <span className="w-6 h-6 rounded-full bg-white shadow" />
        </button>
      </div>
      <div className="grid sm:grid-cols-2 gap-3 mt-4">
        <input data-testid="my-smtp-host-input" value={smtp.host} onChange={(e) => setSmtp({ ...smtp, host: e.target.value })} placeholder="smtp.gmail.com" className="neu-input rounded-2xl py-3 px-4 text-sm" />
        <input data-testid="my-smtp-port-input" type="number" value={smtp.port} onChange={(e) => setSmtp({ ...smtp, port: e.target.value })} placeholder="587" className="neu-input rounded-2xl py-3 px-4 text-sm" />
        <input data-testid="my-smtp-username-input" value={smtp.username} onChange={(e) => setSmtp({ ...smtp, username: e.target.value })} placeholder="you@gmail.com" className="neu-input rounded-2xl py-3 px-4 text-sm" />
        <input data-testid="my-smtp-password-input" type="password" value={smtp.password || ""} onChange={(e) => setSmtp({ ...smtp, password: e.target.value })} placeholder={smtp.has_password ? "•••••• (saved)" : "app password"} className="neu-input rounded-2xl py-3 px-4 text-sm" />
        <input data-testid="my-smtp-from-input" value={smtp.from_address} onChange={(e) => setSmtp({ ...smtp, from_address: e.target.value })} placeholder="from address (e.g. you@gmail.com)" className="neu-input rounded-2xl py-3 px-4 text-sm sm:col-span-2" />
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button data-testid="save-my-smtp-btn" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold">{saving ? "Saving…" : "Save my email"}</button>
        <button data-testid="clear-my-smtp-btn" onClick={clear} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-red-500">Clear credentials</button>
      </div>
      <p className="text-xs text-muted-stitch mt-3">Tip: for Gmail/Outlook create an app password in your account security settings and use it here.</p>
    </div>
  );
}

function DevicesSection() {
  const [sessions, setSessions] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/auth/sessions").then(({ data }) => setSessions(data)).catch(() => setSessions([]));
  useEffect(() => { load(); }, []);

  const revoke = async (id) => {
    try { await api.delete(`/auth/sessions/${id}`); toast.success("Device signed out"); load(); }
    catch (e) { toast.error("Failed to sign out device"); }
  };
  const revokeOthers = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/auth/sessions/revoke-others");
      if (data.token) localStorage.setItem("stitches_token", data.token);
      toast.success("Signed out of all other devices");
      load();
    } catch (e) { toast.error("Failed"); } finally { setBusy(false); }
  };

  const others = (sessions || []).filter((s) => !s.current).length;

  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up" data-testid="devices-section">
      <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><ShieldCheck className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Connected devices</h3>
            <p className="text-sm text-muted-stitch">Devices currently signed in to your account.</p>
          </div>
        </div>
        {others > 0 && (
          <button data-testid="revoke-others-btn" onClick={revokeOthers} disabled={busy}
            className="neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold text-primary-stitch flex items-center gap-2">
            <LogOut className="w-4 h-4" /> {busy ? "Signing out…" : "Sign out all other devices"}
          </button>
        )}
      </div>
      {sessions === null ? (
        <p className="text-sm text-muted-stitch py-4">Loading…</p>
      ) : sessions.length === 0 ? (
        <p className="text-sm text-muted-stitch py-4">No active sessions found.</p>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => {
            const Icon = /iphone|ipad|android/i.test(s.device || "") ? Smartphone : Monitor;
            return (
              <div key={s.session_id} data-testid="device-row" className="neu-pressed rounded-2xl p-4 flex items-center gap-4">
                <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0"><Icon className="w-5 h-5 text-primary-stitch" /></div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold flex items-center gap-2" style={{ color: "var(--text)" }}>
                    {s.device}
                    {s.current && <span data-testid="current-device-badge" className="text-[11px] font-bold px-2 py-0.5 rounded-full text-white" style={{ background: "var(--primary)" }}>This device</span>}
                  </p>
                  <p className="text-xs text-muted-stitch truncate">
                    {s.ip ? `${s.ip} · ` : ""}Last active {new Date(s.last_seen).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
                {!s.current && (
                  <button data-testid="revoke-device-btn" onClick={() => revoke(s.session_id)}
                    className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold text-muted-stitch flex items-center gap-1.5 shrink-0">
                    <LogOut className="w-4 h-4" /> Sign out
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
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
