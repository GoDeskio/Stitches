import { QRCodeSVG } from "qrcode.react";
import { Monitor, Apple, Download, Check, Terminal, ShieldCheck, Zap, Smartphone, Share, PlusSquare } from "lucide-react";
import { PageShell, PageHeader } from "@/components/Stitch";

const APP_URL = typeof window !== "undefined" ? window.location.origin : "";

const MOBILE = [
  {
    key: "android",
    label: "Android",
    icon: Smartphone,
    tint: "#3ddc84",
    steps: ["Scan the code with your camera", "Open the link in Chrome", "Tap ⋮ → \"Install app\" / \"Add to Home screen\""],
  },
  {
    key: "ios",
    label: "iPhone & iPad",
    icon: Apple,
    tint: "#e5e5e5",
    steps: ["Scan the code with your camera", "Open the link in Safari", "Tap Share → \"Add to Home Screen\""],
  },
];

const DESKTOP = [
  { key: "windows", label: "Windows", icon: Monitor, ext: ".exe", note: "Windows 10 & 11 (64-bit)" },
  { key: "macos", label: "macOS", icon: Apple, ext: ".dmg", note: "macOS 11 Big Sur or later" },
  { key: "linux", label: "Linux", icon: Terminal, ext: ".AppImage", note: "Ubuntu / Debian / Fedora" },
];

const FEATURES = [
  { icon: Zap, title: "All your tools, everywhere", body: "Messages, threads, projects, assets, integrations and AI — identical on web, desktop and phone." },
  { icon: ShieldCheck, title: "Always in sync", body: "Every device signs in to the same live account. Presence, messages and tasks update in real time across them all." },
  { icon: Check, title: "Installs like a native app", body: "Add Stitches to your home screen or dock and it opens in its own window — no browser tabs, no clutter." },
];

export default function Downloads() {
  return (
    <PageShell>
      <PageHeader title="Get Stitches on every device" subtitle="Install the app on your phone, desktop and laptop. Everything stays connected to your live account." />

      {/* Mobile install via QR */}
      <div className="mb-12">
        <h2 className="font-head font-bold text-2xl mb-5 flex items-center gap-2" style={{ color: "var(--text)" }}>
          <Smartphone className="w-6 h-6 text-primary-stitch" /> Install on your phone
        </h2>
        <div className="grid sm:grid-cols-2 gap-6">
          {MOBILE.map((m, i) => (
            <div key={m.key} className="neu-raised rounded-[1.75rem] p-7 flex flex-col sm:flex-row items-center gap-6 animate-fade-up" style={{ animationDelay: `${i * 60}ms` }} data-testid={`mobile-${m.key}`}>
              <div className="neu-pressed rounded-2xl p-4 shrink-0" style={{ background: "#fff" }}>
                <QRCodeSVG data-testid={`mobile-qr-${m.key}`} value={APP_URL} size={148} level="M" />
              </div>
              <div className="flex-1 text-center sm:text-left">
                <div className="flex items-center gap-2 justify-center sm:justify-start mb-3">
                  <div className="neu-sm w-10 h-10 rounded-2xl flex items-center justify-center"><m.icon className="w-5 h-5 text-primary-stitch" /></div>
                  <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{m.label}</h3>
                </div>
                <ol className="space-y-1.5">
                  {m.steps.map((s, idx) => (
                    <li key={idx} className="text-sm text-muted-stitch flex items-start gap-2">
                      <span className="neu-sm w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold text-primary-stitch shrink-0 mt-0.5">{idx + 1}</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Feature strip */}
      <div className="grid sm:grid-cols-3 gap-6 mb-12">
        {FEATURES.map((f, i) => (
          <div key={f.title} className="neu-raised rounded-[1.5rem] p-6 animate-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
            <div className="neu-sm w-12 h-12 rounded-2xl flex items-center justify-center mb-4"><f.icon className="w-6 h-6 text-primary-stitch" /></div>
            <h4 className="font-head font-bold text-lg mb-2" style={{ color: "var(--text)" }}>{f.title}</h4>
            <p className="text-sm text-muted-stitch">{f.body}</p>
          </div>
        ))}
      </div>

      {/* Desktop install QR + native client */}
      <div className="mb-8">
        <h2 className="font-head font-bold text-2xl mb-5 flex items-center gap-2" style={{ color: "var(--text)" }}>
          <Monitor className="w-6 h-6 text-primary-stitch" /> Install on desktop
        </h2>
        <div className="neu-raised rounded-[1.75rem] p-7 flex flex-col sm:flex-row items-center gap-7 mb-6 animate-fade-up" data-testid="desktop-install">
          <div className="neu-pressed rounded-2xl p-4 shrink-0" style={{ background: "#fff" }}>
            <QRCodeSVG data-testid="desktop-qr" value={APP_URL} size={148} level="M" />
          </div>
          <div className="flex-1 text-center sm:text-left">
            <h3 className="font-head font-bold text-xl mb-2" style={{ color: "var(--text)" }}>Add to your dock in one click</h3>
            <p className="text-sm text-muted-stitch flex items-center gap-2 justify-center sm:justify-start">
              In Chrome or Edge, open Stitches and click the <PlusSquare className="w-4 h-4 inline text-primary-stitch" /> install icon in the address bar. On Safari, use <Share className="w-4 h-4 inline text-primary-stitch" /> Share → Add to Dock. Or scan the code to open Stitches on any machine.
            </p>
          </div>
        </div>

        <div className="grid sm:grid-cols-3 gap-6">
          {DESKTOP.map((p, i) => (
            <div key={p.key} className="neu-raised neu-hover rounded-[1.75rem] p-7 flex flex-col items-center text-center animate-fade-up" style={{ animationDelay: `${i * 60}ms` }} data-testid={`download-${p.key}`}>
              <div className="neu-sm w-16 h-16 rounded-3xl flex items-center justify-center mb-5"><p.icon className="w-8 h-8 text-primary-stitch" /></div>
              <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>{p.label}</h3>
              <p className="text-sm text-muted-stitch mb-6">{p.note}</p>
              <button data-testid={`download-btn-${p.key}`}
                onClick={() => window.open("https://github.com/", "_blank")}
                className="neu-primary rounded-2xl px-6 py-3 font-semibold flex items-center gap-2 w-full justify-center">
                <Download className="w-5 h-5" /> Download {p.ext}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-8 animate-fade-up">
        <div className="flex items-center gap-3 mb-4">
          <Terminal className="w-6 h-6 text-primary-stitch" />
          <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Build the native client yourself</h3>
        </div>
        <p className="text-muted-stitch mb-5">
          The desktop client is an open Electron app that loads your live Stitches dashboard. To produce a signed installer for your platform, build it from the <span className="font-mono-stitch">/desktop</span> folder in the project:
        </p>
        <div className="neu-pressed rounded-2xl p-5 font-mono-stitch text-sm space-y-1 overflow-x-auto" style={{ color: "var(--text)" }}>
          <p><span className="text-muted-stitch">$</span> cd desktop</p>
          <p><span className="text-muted-stitch">$</span> npm install</p>
          <p><span className="text-muted-stitch">$</span> npm start <span className="text-muted-stitch"># run the client</span></p>
          <p><span className="text-muted-stitch">$</span> npm run dist <span className="text-muted-stitch"># build installers (.exe / .dmg / .AppImage)</span></p>
        </div>
        <p className="text-xs text-muted-stitch mt-4">The client reads your dashboard URL from <span className="font-mono-stitch">STITCHES_URL</span> (defaults to this deployment). Sessions persist between launches, so you stay signed in.</p>
      </div>
    </PageShell>
  );
}
