import { Loader2 } from "lucide-react";

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-8 animate-fade-up">
      <div>
        <h1 className="font-head font-black text-4xl sm:text-5xl tracking-tight" style={{ color: "var(--text)" }}>{title}</h1>
        {subtitle && <p className="mt-2 text-muted-stitch max-w-xl">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageShell({ children }) {
  return <div className="p-6 sm:p-10 max-w-7xl mx-auto">{children}</div>;
}

export function Loader() {
  return (
    <div className="flex items-center justify-center py-24">
      <div className="stitch-spinner" />
    </div>
  );
}

export function InlineSpin() {
  return <Loader2 className="w-5 h-5 animate-spin" />;
}

export function EmptyState({ icon: Icon, title, subtitle, action }) {
  return (
    <div className="neu-pressed rounded-[1.75rem] py-20 px-8 flex flex-col items-center text-center animate-fade-up">
      <div className="neu-raised w-20 h-20 rounded-3xl flex items-center justify-center mb-6">
        <Icon className="w-9 h-9 text-primary-stitch" />
      </div>
      <h3 className="font-head font-bold text-2xl mb-2" style={{ color: "var(--text)" }}>{title}</h3>
      <p className="text-muted-stitch max-w-sm mb-6">{subtitle}</p>
      {action}
    </div>
  );
}
