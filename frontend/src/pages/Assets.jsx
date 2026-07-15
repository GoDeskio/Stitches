import { useEffect, useRef, useState } from "react";
import { Upload, FileText, Image as ImageIcon, Download, Share2, Trash2, FolderOpen, Cloud } from "lucide-react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import api, { API } from "@/lib/api";
import { PageShell, PageHeader, Loader, EmptyState } from "@/components/Stitch";
import { useAuth } from "@/context/AuthContext";

export default function Assets() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [assets, setAssets] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);
  const token = localStorage.getItem("stitches_token");

  const load = () => api.get("/assets").then(({ data }) => setAssets(data));
  useEffect(() => { load(); }, []);

  const upload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        await api.post("/assets/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      toast.success(`${files.length} file(s) uploaded`);
      load();
    } catch (err) { toast.error("Upload failed"); } finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const share = async (id) => { await api.post(`/assets/${id}/share`); toast.success("Asset shared with workspace"); load(); };
  const remove = async (id) => { await api.delete(`/assets/${id}`); toast.success("Asset deleted"); load(); };
  const download = (a) => window.open(`${API}/assets/${a.asset_id}/download?auth=${token}`, "_blank");

  if (assets === null) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <PageHeader title="Assets" subtitle="Upload from your computer or connect a cloud account. Share files across your workspaces."
        action={
          <div className="flex gap-3">
            <button data-testid="connect-cloud-btn" onClick={() => navigate("/integrations")} className="neu-btn rounded-2xl px-5 py-3 font-semibold flex items-center gap-2" style={{ color: "var(--text)" }}>
              <Cloud className="w-5 h-5 text-primary-stitch" /> Connect Cloud
            </button>
            <button data-testid="upload-asset-btn" onClick={() => fileRef.current?.click()} disabled={uploading} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2">
              <Upload className="w-5 h-5" /> {uploading ? "Uploading..." : "Upload"}
            </button>
            <input ref={fileRef} type="file" multiple hidden onChange={upload} data-testid="file-input" />
          </div>
        } />

      {assets.length === 0 ? (
        <EmptyState icon={FolderOpen} title="Your assets folder is empty" subtitle="Upload images, documents and files from your computer to share with your team."
          action={<button onClick={() => fileRef.current?.click()} className="neu-primary rounded-2xl px-6 py-3 font-semibold">Upload a file</button>} />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {assets.map((a, i) => {
            const isImage = (a.content_type || "").startsWith("image/");
            const mine = a.owner_id === user?.user_id;
            return (
              <div key={a.asset_id} className="neu-raised neu-hover rounded-[1.5rem] p-4 animate-fade-up flex flex-col" style={{ animationDelay: `${i * 40}ms` }} data-testid="asset-card">
                <div className="neu-pressed rounded-2xl h-36 mb-4 flex items-center justify-center overflow-hidden">
                  {isImage ? (
                    <img src={`${API}/assets/${a.asset_id}/download?auth=${token}`} alt={a.original_filename} className="w-full h-full object-cover rounded-2xl" />
                  ) : (
                    <FileText className="w-12 h-12 text-primary-stitch" />
                  )}
                </div>
                <div className="flex items-center gap-2 mb-1">
                  {isImage ? <ImageIcon className="w-4 h-4 text-muted-stitch shrink-0" /> : <FileText className="w-4 h-4 text-muted-stitch shrink-0" />}
                  <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{a.original_filename}</p>
                </div>
                <p className="text-xs text-muted-stitch mb-4">{((a.size || 0) / 1024).toFixed(1)} KB {a.is_shared && "• Shared"}</p>
                <div className="flex gap-2 mt-auto">
                  <button onClick={() => download(a)} className="neu-btn flex-1 rounded-xl py-2 flex items-center justify-center text-primary-stitch" title="Download"><Download className="w-4 h-4" /></button>
                  {mine && <button onClick={() => share(a.asset_id)} className="neu-btn flex-1 rounded-xl py-2 flex items-center justify-center text-muted-stitch" title="Share"><Share2 className="w-4 h-4" /></button>}
                  {mine && <button onClick={() => remove(a.asset_id)} className="neu-btn flex-1 rounded-xl py-2 flex items-center justify-center text-muted-stitch" title="Delete"><Trash2 className="w-4 h-4" /></button>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
