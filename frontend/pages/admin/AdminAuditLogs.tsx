import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function AdminAuditLogs() {
  const [logs, setLogs] = useState<any[]>([]);
  const [actionFilter, setActionFilter] = useState("all");

  useEffect(() => {
    let query = supabase.from("audit_logs").select("*").order("created_at", { ascending: false }).limit(100);
    if (actionFilter !== "all") query = query.eq("action_type", actionFilter);
    query.then(({ data }) => setLogs(data ?? []));
  }, [actionFilter]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Audit Logs</h1>
      <Select value={actionFilter} onValueChange={setActionFilter}>
        <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Actions</SelectItem>
          <SelectItem value="credential_created">Credential Created</SelectItem>
          <SelectItem value="credential_rotated">Credential Rotated</SelectItem>
          <SelectItem value="credential_revoked">Credential Revoked</SelectItem>
        </SelectContent>
      </Select>
      <div className="rounded-xl border overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-secondary/50">
              <th className="px-4 py-3 text-left font-medium">Action</th>
              <th className="px-4 py-3 text-left font-medium">Actor</th>
              <th className="px-4 py-3 text-left font-medium">Target</th>
              <th className="px-4 py-3 text-left font-medium">Metadata</th>
              <th className="px-4 py-3 text-left font-medium">Time</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-medium">{log.action_type}</td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{log.actor_user_id?.slice(0, 8)}...</td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{log.target_user_id?.slice(0, 8)}...</td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground max-w-xs truncate">{JSON.stringify(log.metadata_json)}</td>
                <td className="px-4 py-3 text-muted-foreground">{new Date(log.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {logs.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No audit logs found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
