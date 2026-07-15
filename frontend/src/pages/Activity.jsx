import { useEffect, useState } from "react";
import {
  Activity as ActivityIcon, LogIn, MessageSquare, FolderKanban, StickyNote, Plug,
  Play, Upload, Sparkles, UserPlus, Shield, Circle,
} from "lucide-react";
import api from "@/lib/api";
import { PageShell, PageHeader, Loader, EmptyState } from "@/components/Stitch";

const ACTION_META = {
  login: { icon: LogIn, label: "Signed in" },
  register: { icon: UserPlus, label: "Created account" },
  message: { icon: MessageSquare, label: "Sent a message" },
  project_create: { icon: FolderKanban, label: "Created a project" },
  project_update: { icon: FolderKanban, label: "Updated a project" },
  note_create: { icon: StickyNote, label: "Created a note" },
  note_update: { icon: StickyNote, label: "Updated a note" },
  integration_connect: { icon: Plug, label: "Connected an integration" },
  integration_run: { icon: Play, label: "Ran an integration" },
  asset_upload: { icon: Upload, label: "Uploaded an asset" },
  ai_chat: { icon: Sparkles, label: "Used the AI assistant" },
  friend_add: { icon: UserPlus, label: "Added a connection" },
};

function meta(action) {
  return ACTION_META[action] || { icon: Circle, label: action.replace(/_/g, " ") };
}

export default function Activity() {
  const [logs, setLogs] = useState(null);
  useEffect(() => { api.get("/activity/me").then(({ data }) => setLogs(data)); }, []);

  if (logs === null) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <PageHeader title="Activity Log" subtitle="A private, complete history of everything that happens on your account — sign-ins, messages, projects, integrations and more." />
      {logs.length === 0 ? (
        <EmptyState icon={ActivityIcon} title="No activity yet" subtitle="Your account activity will appear here as you use Stitches." />
      ) : (
        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up space-y-3" data-testid="activity-list">
          {logs.map((l, i) => {
            const { icon: Icon, label } = meta(l.action);
            const hasMeta = l.meta && Object.keys(l.meta).length > 0;
            return (
              <div key={i} className="neu-pressed rounded-2xl p-4 flex items-center gap-4 animate-fade-up" style={{ animationDelay: `${Math.min(i, 15) * 25}ms` }} data-testid="activity-row">
                <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0"><Icon className="w-5 h-5 text-primary-stitch" /></div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{label}</p>
                  {hasMeta && <p className="text-xs text-muted-stitch truncate font-mono-stitch">{JSON.stringify(l.meta)}</p>}
                </div>
                <span className="text-xs text-muted-stitch shrink-0 whitespace-nowrap">{new Date(l.created_at).toLocaleString()}</span>
              </div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
