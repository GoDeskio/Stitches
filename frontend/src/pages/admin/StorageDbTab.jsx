import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";
import { Database, HardDrive, Trash2, DownloadCloud, History, X, AlertTriangle, Users } from "lucide-react";

const fmtBytes = (n) => {
  n = Number(n) || 0;
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1073741824) return `${(n / 1048576).toFixed(1)} MB`;
  return `${(n / 1073741824).toFixed(2)} GB`;
};

export function StorageDbTab() {
  return (
    <div className="space-y-6" data-testid="storage-db-tab">
      <DbSection />
      <DbBackupsSection />
      <StorageSection />
    </div>
  );
}

function DbSection() {
  const [data, setData] = useState(null);
  const [browse, setBrowse] = useState(null); // collection name

  const load = () => api.get("/admin/db/overview").then(({ data }) => setData(data)).catch(() => setData({ collections: [] }));
  useEffect(() => { load(); }, []);

  const purge = async (name) => {
    if (!window.confirm(`Empty the "${name}" collection? This permanently deletes ALL documents in it and cannot be undone.${name === "users" ? "\n\n(The super-admin account is preserved.)" : ""}`)) return;
    try { const { data } = await api.post(`/admin/db/collections/${name}/purge`); toast.success(`Purged ${data.deleted} document(s) from ${name}`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Purge failed"); }
  };

  if (!data) return <Loader />;
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="db-section">
      <div className="flex items-center gap-3 mb-4">
        <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Database className="w-5 h-5 text-primary-stitch" /></div>
        <div>
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Database — {data.db_name}</h3>
          <p className="text-sm text-muted-stitch">{data.objects?.toLocaleString?.() || 0} documents · data {fmtBytes(data.data_size)} · storage {fmtBytes(data.storage_size)} · indexes {fmtBytes(data.index_size)}</p>
        </div>
      </div>
      <div className="space-y-2">
        {(data.collections || []).map((c) => (
          <div key={c.name} data-testid={`db-collection-${c.name}`} className="neu-pressed rounded-2xl px-4 py-3 flex items-center gap-3 flex-wrap">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold flex items-center gap-2" style={{ color: "var(--text)" }}>
                {c.name}
                {c.protected && <span className="text-[10px] uppercase font-bold text-amber-500">protected</span>}
              </p>
              <p className="text-[11px] text-muted-stitch">{c.count.toLocaleString()} docs · {fmtBytes(c.size)} · {c.indexes} indexes</p>
            </div>
            <button data-testid={`db-browse-${c.name}`} onClick={() => setBrowse(c.name)} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch shrink-0">Browse</button>
            <button data-testid={`db-purge-${c.name}`} onClick={() => purge(c.name)} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-red-500 shrink-0 flex items-center gap-1"><Trash2 className="w-3.5 h-3.5" /> Empty</button>
          </div>
        ))}
      </div>
      {browse && <DocBrowser name={browse} onClose={() => { setBrowse(null); load(); }} />}
    </div>
  );
}

function DocBrowser({ name, onClose }) {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);

  const load = () => api.get(`/admin/db/collections/${name}/docs`, { params: { page } }).then(({ data }) => setData(data)).catch(() => setData({ docs: [] }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [page, name]);

  const del = async (id) => {
    if (!window.confirm(`Delete this document (id ${id}) from ${name}? This cannot be undone.`)) return;
    try { await api.post(`/admin/db/collections/${name}/delete-doc`, { id }); toast.success("Document deleted"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose} data-testid="db-doc-browser">
      <div className="neu-raised rounded-[1.75rem] p-6 max-w-3xl w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{name} <span className="text-sm text-muted-stitch">· {data?.total ?? "…"} docs</span></h3>
          <button onClick={onClose} data-testid="db-doc-close" className="text-muted-stitch hover:text-primary-stitch"><X className="w-5 h-5" /></button>
        </div>
        {!data ? <Loader /> : data.docs.length === 0 ? <p className="text-sm text-muted-stitch py-8 text-center">Empty collection.</p> : (
          <div className="space-y-2">
            {data.docs.map((d) => (
              <div key={d._id} data-testid="db-doc-row" className="neu-pressed rounded-2xl p-3 flex items-start gap-3">
                <pre className="text-[11px] font-mono-stitch overflow-x-auto flex-1 min-w-0" style={{ color: "var(--text)" }}>{JSON.stringify(d, null, 2)}</pre>
                <button data-testid="db-doc-delete" onClick={() => del(d._id)} className="neu-btn rounded-xl px-2.5 py-2 text-red-500 shrink-0"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
            {data.pages > 1 && (
              <div className="flex items-center justify-center gap-3 pt-2">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="neu-btn rounded-xl px-4 py-2 text-sm disabled:opacity-40">Prev</button>
                <span className="text-sm text-muted-stitch">{page} / {data.pages}</span>
                <button disabled={page >= data.pages} onClick={() => setPage(page + 1)} className="neu-btn rounded-xl px-4 py-2 text-sm disabled:opacity-40">Next</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DbBackupsSection() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/admin/db/backups").then(({ data }) => setData(data)).catch(() => setData({ backups: [], mongodump: false }));
  useEffect(() => { load(); }, []);

  const backup = async () => {
    setBusy(true);
    try { const { data } = await api.post("/admin/db/backup"); toast.success(`Backup created (${data.stamp})`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Backup failed"); } finally { setBusy(false); }
  };
  const restore = async (stamp) => {
    if (!window.confirm(`Restore the database from backup ${stamp}? This DROPS current collections and replaces them with the snapshot.`)) return;
    try { await api.post(`/admin/db/restore/${stamp}`); toast.success("Database restored"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Restore failed"); }
  };

  if (!data) return null;
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="db-backups-section">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-3">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><History className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Database backups</h3>
            <p className="text-sm text-muted-stitch">Create an on-demand MongoDB snapshot and restore it any time.</p>
          </div>
        </div>
        <button data-testid="db-backup-btn" onClick={backup} disabled={busy || !data.mongodump} className="neu-primary rounded-2xl px-5 py-3 font-semibold text-sm flex items-center gap-2 disabled:opacity-50"><DownloadCloud className="w-4 h-4" /> {busy ? "Backing up…" : "Back up now"}</button>
      </div>
      {!data.mongodump && <p className="text-xs text-amber-500 flex items-center gap-1.5 mb-3" data-testid="db-nodump"><AlertTriangle className="w-3.5 h-3.5" /> mongodump isn't installed on this server, so backups/restore are disabled here. (Available on a self-hosted install.)</p>}
      {data.backups.length === 0 ? <p className="text-sm text-muted-stitch py-4 text-center">No database backups yet.</p> : (
        <div className="space-y-2">
          {data.backups.map((b) => (
            <div key={b.stamp} data-testid="db-backup-row" className="neu-pressed rounded-2xl px-4 py-3 flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>{b.stamp}</p>
                <p className="text-[11px] text-muted-stitch">{fmtBytes(b.size)}</p>
              </div>
              <button data-testid="db-restore-btn" onClick={() => restore(b.stamp)} className="neu-btn rounded-xl px-4 py-2 text-sm font-semibold text-primary-stitch shrink-0">Restore</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StorageSection() {
  const [data, setData] = useState(null);

  const load = () => api.get("/admin/storage/overview").then(({ data }) => setData(data)).catch(() => setData({ by_user: [] }));
  useEffect(() => { load(); }, []);

  const act = async (fn, label) => {
    try { const { data } = await fn(); toast.success(`${label} — ${data.deleted} file(s) removed`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const delUser = (u) => { if (window.confirm(`Delete ALL ${u.count} file(s) for ${u.name} (${u.email || u.owner_id})? This permanently removes them from storage.`)) act(() => api.post(`/admin/storage/delete-by-user/${u.owner_id}`), "Deleted user files"); };
  const delOrphans = () => { if (window.confirm("Delete all files owned by deleted/unknown users (orphaned files)?")) act(() => api.post("/admin/storage/delete-orphans"), "Deleted orphans"); };
  const delAll = () => { if (window.confirm("Delete ALL uploaded files for every user? This is irreversible.")) act(() => api.post("/admin/storage/delete-all"), "Deleted all files"); };

  if (!data) return <Loader />;
  const hasOrphans = (data.by_user || []).some((u) => u.orphan);
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="storage-section">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-3">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><HardDrive className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>File storage</h3>
            <p className="text-sm text-muted-stitch">{data.total_count?.toLocaleString?.() || 0} files · {fmtBytes(data.total_bytes)} across {data.by_user?.length || 0} user(s)</p>
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          {hasOrphans && <button data-testid="storage-delete-orphans" onClick={delOrphans} className="neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold text-amber-500">Delete orphans</button>}
          <button data-testid="storage-delete-all" onClick={delAll} className="neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold text-red-500 flex items-center gap-1.5"><Trash2 className="w-4 h-4" /> Delete all</button>
        </div>
      </div>
      {data.by_user.length === 0 ? <p className="text-sm text-muted-stitch py-6 text-center">No uploaded files yet.</p> : (
        <div className="space-y-2">
          {data.by_user.map((u) => (
            <div key={u.owner_id || "none"} data-testid="storage-user-row" className="neu-pressed rounded-2xl px-4 py-3 flex items-center gap-3">
              <div className="w-9 h-9 rounded-full neu-sm flex items-center justify-center shrink-0"><Users className="w-4 h-4 text-primary-stitch" /></div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate flex items-center gap-2" style={{ color: "var(--text)" }}>{u.name}{u.orphan && <span className="text-[10px] uppercase font-bold text-amber-500">orphan</span>}</p>
                <p className="text-[11px] text-muted-stitch truncate">{u.email || u.owner_id} · {u.count} file(s) · {fmtBytes(u.bytes)}</p>
              </div>
              <button data-testid="storage-delete-user" onClick={() => delUser(u)} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-red-500 shrink-0 flex items-center gap-1"><Trash2 className="w-3.5 h-3.5" /> Delete</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
