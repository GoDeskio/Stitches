import { Shield } from "lucide-react";

export function Avatar({ u }) {
  return (
    <div className="neu-sm w-11 h-11 rounded-full flex items-center justify-center overflow-hidden shrink-0">
      {u.avatar ? <img src={u.avatar} alt="" className="w-full h-full object-cover" /> :
        <span className="font-head font-bold text-primary-stitch">{(u.name || "U")[0].toUpperCase()}</span>}
    </div>
  );
}

export function RolePill({ role }) {
  return (
    <span className={`text-xs px-3 py-1.5 rounded-full font-semibold flex items-center gap-1 ${role === "admin" ? "neu-primary" : "neu-sm text-muted-stitch"}`}>
      {role === "admin" && <Shield className="w-3 h-3" />}{role}
    </span>
  );
}

export function ActionBtn({ onClick, icon: Icon, title, testid, primary }) {
  return (
    <button data-testid={testid} onClick={onClick} title={title}
      className={`w-10 h-10 rounded-xl flex items-center justify-center ${primary ? "neu-primary" : "neu-btn text-primary-stitch"}`}>
      <Icon className="w-4 h-4" />
    </button>
  );
}
