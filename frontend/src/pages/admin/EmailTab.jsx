import { useState, useEffect } from "react";
import { toast } from "sonner";
import api, { API, BACKEND_ORIGIN } from "@/lib/api";
import { Mail, Activity, Check } from "lucide-react";

export function EmailTab() {
  return (
    <div className="space-y-6" data-testid="email-tab">
      <EmailSetupWizard />
      <ResendSetupCard />
      <EmailAnalyticsCard />
      <TestEmailCard />
      <DigestCard />
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

function ResendSetupCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);

  const load = async () => {
    setLoading(true);
    try { const { data } = await api.get("/admin/resend/dns"); setData(data); }
    catch (e) { setData({ ok: false, error: "Could not load Resend status", records: [] }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const verify = async () => {
    setVerifying(true);
    try { await api.post("/admin/resend/verify"); toast.success("Verification requested — DNS can take a few minutes"); setTimeout(load, 2500); }
    catch (e) { toast.error(e?.response?.data?.detail || "Verify failed"); }
    finally { setVerifying(false); }
  };

  if (!data) return null;
  const badge = (() => {
    const s = data.status;
    if (data.verified || s === "verified") return { t: "Verified ✓", c: "text-green-500", bg: "#16a34a" };
    if (s === "pending") return { t: "Pending — DNS propagating", c: "text-amber-500", bg: "#f59e0b" };
    if (s === "failure") return { t: "Failed — records not found", c: "text-red-400", bg: "#ef4444" };
    if (s === "not_started") return { t: "Not started — add the records below", c: "text-muted-stitch", bg: "#9ca3af" };
    return { t: data.error ? "Unavailable" : (s || "unknown"), c: "text-muted-stitch", bg: "#9ca3af" };
  })();

  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="resend-setup-card">
      <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Mail className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Resend domain setup</h3>
            <p className="text-sm text-muted-stitch">Add these DNS records at your registrar to make email deliver from <span className="font-mono-stitch" data-testid="resend-domain">{data.domain || "your domain"}</span>.</p>
          </div>
        </div>
        <span data-testid="resend-status-badge" className={`text-sm font-semibold px-3 py-1.5 rounded-full ${badge.c}`} style={{ background: "var(--neu-dark)" }}>{badge.t}</span>
      </div>

      {data.error && <p className="text-xs text-amber-500 mt-3" data-testid="resend-error">{data.error}</p>}

      {data.records && data.records.length > 0 && (
        <div className="mt-4 space-y-2" data-testid="resend-records">
          {data.records.map((r, i) => (
            <div key={i} data-testid="resend-record-row" className="neu-pressed rounded-2xl px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: r.status === "verified" ? "#16a34a" : "#f59e0b", boxShadow: `0 0 8px ${r.status === "verified" ? "#16a34a" : "#f59e0b"}` }} />
                <span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text)" }}>{r.record || r.type}</span>
                <span className="text-[11px] text-muted-stitch">· {r.type}{r.priority != null ? ` · priority ${r.priority}` : ""} · TTL {r.ttl}</span>
                <span className={`ml-auto text-[11px] font-bold ${r.status === "verified" ? "text-green-500" : "text-amber-500"}`}>{r.status || "pending"}</span>
              </div>
              <p className="text-[11px] text-muted-stitch mb-0.5">Host / Name</p>
              <CopyRow value={r.name} testid={`resend-rec-name-${i}`} />
              <p className="text-[11px] text-muted-stitch mb-0.5 mt-2">Value</p>
              <CopyRow value={r.value} testid={`resend-rec-value-${i}`} />
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-center gap-3 flex-wrap">
        <button data-testid="resend-refresh-btn" onClick={load} disabled={loading} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch">{loading ? "Checking…" : "Refresh status"}</button>
        <button data-testid="resend-verify-btn" onClick={verify} disabled={verifying || !data.domain_id} className="neu-primary rounded-2xl px-6 py-3 font-semibold">{verifying ? "Verifying…" : "Verify now"}</button>
      </div>
      <p className="text-xs text-muted-stitch mt-3">After the badge shows <span className="text-green-500 font-semibold">Verified ✓</span>, use “Test email delivery” below to confirm end-to-end. Records are pulled live from your Resend account.</p>
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
  const webhookUrl = `${BACKEND_ORIGIN}/api/webhooks/mailgun`;
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

