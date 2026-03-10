import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Users, Key, ShieldAlert, Activity } from "lucide-react";

export default function AdminDashboard() {
  const [stats, setStats] = useState({ users: 0, active: 0, creds: 0, revoked: 0 });
  const [recentLogs, setRecentLogs] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      supabase.from("profiles").select("id, status"),
      supabase.from("bugpilot_credentials").select("id, status"),
      supabase.from("audit_logs").select("*").order("created_at", { ascending: false }).limit(5),
    ]).then(([profilesRes, credsRes, logsRes]) => {
      const profiles = profilesRes.data ?? [];
      const creds = credsRes.data ?? [];
      setStats({
        users: profiles.length,
        active: profiles.filter((p: any) => p.status === "active").length,
        creds: creds.filter((c: any) => c.status === "active").length,
        revoked: creds.filter((c: any) => c.status === "revoked").length,
      });
      setRecentLogs(logsRes.data ?? []);
    });
  }, []);

  const statCards = [
    { label: "Total Users", value: stats.users, icon: Users, color: "text-primary" },
    { label: "Active Users", value: stats.active, icon: Activity, color: "text-success" },
    { label: "Active Credentials", value: stats.creds, icon: Key, color: "text-info" },
    { label: "Revoked Credentials", value: stats.revoked, icon: ShieldAlert, color: "text-destructive" },
  ];

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Admin Overview</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((s) => (
          <div key={s.label} className="rounded-xl border p-5">
            <s.icon className={`h-6 w-6 ${s.color}`} />
            <div className="mt-3 text-2xl font-bold">{s.value}</div>
            <div className="text-sm text-muted-foreground">{s.label}</div>
          </div>
        ))}
      </div>
      <div>
        <h2 className="text-lg font-semibold">Recent Activity</h2>
        {recentLogs.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No recent activity.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {recentLogs.map((log) => (
              <div key={log.id} className="flex items-center justify-between rounded-lg border px-4 py-3 text-sm">
                <span className="font-medium">{log.action_type}</span>
                <span className="text-muted-foreground">{new Date(log.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
