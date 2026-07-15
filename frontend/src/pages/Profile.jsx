import { useNavigate } from "react-router-dom";
import { Mail, Phone, MapPin, Building2, Briefcase, AtSign, Pencil, Shield } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { PageShell, PageHeader } from "@/components/Stitch";

export default function Profile() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const initials = (user?.name || user?.email || "U").slice(0, 1).toUpperCase();

  const rows = [
    { icon: AtSign, label: "Username", value: user?.username },
    { icon: Mail, label: "Email", value: user?.email },
    { icon: Phone, label: "Phone", value: user?.phone },
    { icon: MapPin, label: "Address", value: user?.address },
    { icon: Building2, label: "Company", value: user?.company },
    { icon: Briefcase, label: "Role", value: user?.company_role },
  ];

  return (
    <PageShell>
      <PageHeader title="Profile" subtitle="Your personal Stitches identity."
        action={<button data-testid="edit-profile-btn" onClick={() => navigate("/settings")} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Pencil className="w-4 h-4" /> Edit</button>} />

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="neu-raised rounded-[1.75rem] p-8 flex flex-col items-center text-center animate-fade-up">
          <div className="neu-raised w-28 h-28 rounded-full flex items-center justify-center overflow-hidden mb-5">
            {user?.avatar ? <img src={user.avatar} alt="" className="w-full h-full object-cover" /> :
              <span className="font-head font-black text-4xl text-primary-stitch">{initials}</span>}
          </div>
          <h2 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>{user?.name}</h2>
          <p className="text-muted-stitch">@{user?.username}</p>
          {user?.role === "admin" && (
            <span className="neu-sm mt-4 text-xs px-4 py-1.5 rounded-full text-primary-stitch font-semibold flex items-center gap-1"><Shield className="w-3 h-3" /> Administrator</span>
          )}
          {user?.bio && <p className="text-sm text-muted-stitch mt-5">{user.bio}</p>}
        </div>

        <div className="lg:col-span-2 neu-raised rounded-[1.75rem] p-8 animate-fade-up">
          <h3 className="font-head font-bold text-xl mb-6" style={{ color: "var(--text)" }}>Details</h3>
          <div className="grid sm:grid-cols-2 gap-4">
            {rows.map(({ icon: Icon, label, value }) => (
              <div key={label} className="neu-pressed rounded-2xl p-4 flex items-center gap-4">
                <div className="neu-sm w-10 h-10 rounded-xl flex items-center justify-center shrink-0"><Icon className="w-5 h-5 text-primary-stitch" /></div>
                <div className="min-w-0">
                  <p className="text-xs text-muted-stitch">{label}</p>
                  <p className="font-medium truncate" style={{ color: "var(--text)" }}>{value || "—"}</p>
                </div>
              </div>
            ))}
          </div>
          {user?.project_info && (
            <div className="neu-pressed rounded-2xl p-5 mt-4">
              <p className="text-xs text-muted-stitch mb-1">Project Info</p>
              <p style={{ color: "var(--text)" }}>{user.project_info}</p>
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}
