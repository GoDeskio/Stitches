import { useState, useEffect } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";
import { Megaphone, Bell, Activity, ShieldCheck } from "lucide-react";

export function SiteNoteTab() {
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

