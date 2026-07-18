import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UserCheck, Ban, BadgeCheck, KeyRound, LogIn } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Loader } from "@/components/Stitch";
import { Avatar, RolePill, ActionBtn } from "@/pages/admin/UserBits";

export function UsersTab() {
  const [users, setUsers] = useState(null);
  const [plans, setPlans] = useState([]);
  const navigate = useNavigate();
  const { startImpersonation } = useAuth();
  const load = () => api.get("/admin/users").then(({ data }) => setUsers(data));
  useEffect(() => {
    load();
    api.get("/admin/plans").then(({ data }) => setPlans(data.plans || [])).catch(() => {});
  }, []);

  const setPlan = async (u, planId) => {
    await api.post(`/admin/users/${u.user_id}/plan`, { plan_id: planId });
    toast.success(planId ? "Plan assigned" : "Plan cleared"); load();
  };

  const toggleActive = async (u) => {
    await api.put(`/admin/users/${u.user_id}`, { is_active: u.is_active === false });
    toast.success(u.is_active === false ? "Account reinstated" : "Account disabled"); load();
  };
  const toggleRole = async (u) => {
    await api.put(`/admin/users/${u.user_id}`, { role: u.role === "admin" ? "user" : "admin" });
    toast.success("Role updated"); load();
  };
  const resetPw = async (u) => {
    const pw = window.prompt(`Set a new password for ${u.email}:`);
    if (!pw) return;
    await api.post(`/admin/users/${u.user_id}/set-password`, { password: pw });
    toast.success("Password updated — share it securely with the user");
  };
  const impersonate = async (u) => {
    const { data } = await api.post(`/admin/users/${u.user_id}/impersonate`);
    startImpersonation(data.token, data.user);
    toast.success(`Now viewing as ${u.name}`);
    navigate("/dashboard");
  };

  if (!users) return <Loader />;
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up space-y-3">
      {users.map((u) => (
        <div key={u.user_id} className="neu-pressed rounded-2xl p-4 flex flex-wrap items-center gap-4" data-testid="admin-user-row">
          <Avatar u={u} />
          <div className="flex-1 min-w-0">
            <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{u.name}</p>
            <p className="text-sm text-muted-stitch truncate">{u.email}</p>
          </div>
          {u.is_active === false && <span className="text-xs px-3 py-1 rounded-full neu-sm text-red-500 font-semibold">Disabled</span>}
          <RolePill role={u.role} />
          {plans.length > 0 && (
            <select data-testid="user-plan-select" value={u.plan_id || ""} onChange={(e) => setPlan(u, e.target.value)}
              title="Assign a plan (used when feature gating is on)"
              className="neu-input rounded-xl py-2 px-3 text-sm">
              <option value="">No plan</option>
              {plans.map((p) => <option key={p.plan_id} value={p.plan_id}>{p.name}</option>)}
            </select>
          )}
          <div className="flex gap-2 items-center flex-wrap">
            <button
              data-testid="btn-active"
              onClick={() => toggleActive(u)}
              className={`text-sm font-semibold rounded-xl px-4 py-2 flex items-center gap-2 transition-transform hover:scale-[1.03] ${u.is_active === false ? "neu-primary" : "neu-sm text-red-500"}`}
              title={u.is_active === false ? "Reinstate this account" : "Disable this account"}
            >
              {u.is_active === false ? <><UserCheck className="w-4 h-4" /> Reinstate Account</> : <><Ban className="w-4 h-4" /> Disable Account</>}
            </button>
            <ActionBtn onClick={() => toggleRole(u)} icon={BadgeCheck} title="Toggle admin" testid="btn-role" />
            <ActionBtn onClick={() => resetPw(u)} icon={KeyRound} title="Reset password" testid="btn-reset" />
            <ActionBtn onClick={() => impersonate(u)} icon={LogIn} title="Login as user" testid="btn-impersonate" primary />
          </div>
        </div>
      ))}
    </div>
  );
}
