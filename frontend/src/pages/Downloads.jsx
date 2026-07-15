import { Monitor, Apple, Download, Check, Terminal, ShieldCheck, Zap } from "lucide-react";
import { PageShell, PageHeader } from "@/components/Stitch";

const PLATFORMS = [
  { key: "windows", label: "Windows", icon: Monitor, ext: ".exe", note: "Windows 10 & 11 (64-bit)" },
  { key: "macos", label: "macOS", icon: Apple, ext: ".dmg", note: "macOS 11 Big Sur or later" },
  { key: "linux", label: "Linux", icon: Terminal, ext: ".AppImage", note: "Ubuntu / Debian / Fedora" },
];

const FEATURES = [
  { icon: Zap, title: "Same tools, native feel", body: "Every feature from your online dashboard — messages, threads, projects, assets, integrations and AI — in a focused desktop window." },
  { icon: ShieldCheck, title: "Always connected to your account", body: "The client signs in to your live Stitches account and stays connected. Your data lives online, encrypted and in sync." },
  { icon: Check, title: "Distraction-free", body: "Opens straight into your dashboard — no browser tabs, no marketing pages, just your workspace." },
];

export default function Downloads() {
  return (
    <PageShell>
      <PageHeader title="Stitches Desktop" subtitle="A dedicated desktop client that opens straight into your dashboard and stays connected to your online account." />

      <div className="grid sm:grid-cols-3 gap-6 mb-12">
        {PLATFORMS.map((p, i) => (
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

      <div className="grid sm:grid-cols-3 gap-6 mb-12">
        {FEATURES.map((f, i) => (
          <div key={f.title} className="neu-raised rounded-[1.5rem] p-6 animate-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
            <div className="neu-sm w-12 h-12 rounded-2xl flex items-center justify-center mb-4"><f.icon className="w-6 h-6 text-primary-stitch" /></div>
            <h4 className="font-head font-bold text-lg mb-2" style={{ color: "var(--text)" }}>{f.title}</h4>
            <p className="text-sm text-muted-stitch">{f.body}</p>
          </div>
        ))}
      </div>

      <div className="neu-raised rounded-[1.75rem] p-8 animate-fade-up">
        <div className="flex items-center gap-3 mb-4">
          <Terminal className="w-6 h-6 text-primary-stitch" />
          <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Build it yourself</h3>
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
