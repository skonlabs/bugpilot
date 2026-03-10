import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Search } from "lucide-react";

export default function AdminUsers() {
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const fetchUsers = async () => {
    setLoading(true);
    let query = supabase.from("profiles").select("*").order("created_at", { ascending: false });
    if (statusFilter !== "all") query = query.eq("status", statusFilter);
    if (search) query = query.ilike("email", `%${search}%`);
    const { data } = await query;
    setUsers(data ?? []);
    setLoading(false);
  };

  useEffect(() => { fetchUsers(); }, [statusFilter, search]);

  const updateStatus = async (userId: string, newStatus: string) => {
    const { error } = await supabase.from("profiles").update({ status: newStatus }).eq("auth_user_id", userId);
    if (error) toast.error(error.message);
    else { toast.success("User updated"); fetchUsers(); }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">User Management</h1>

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search by email..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
            <SelectItem value="suspended">Suspended</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-xl border">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-secondary/50">
                <th className="px-4 py-3 text-left font-medium">Email</th>
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Joined</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b last:border-0">
                  <td className="px-4 py-3 font-mono text-xs">{u.email}</td>
                  <td className="px-4 py-3">{u.full_name || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${u.status === "active" ? "bg-success/10 text-success" : u.status === "suspended" ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground"}`}>
                      {u.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-right">
                    {u.status === "active" ? (
                      <Button variant="ghost" size="sm" onClick={() => updateStatus(u.auth_user_id, "suspended")}>Suspend</Button>
                    ) : (
                      <Button variant="ghost" size="sm" onClick={() => updateStatus(u.auth_user_id, "active")}>Activate</Button>
                    )}
                  </td>
                </tr>
              ))}
              {users.length === 0 && !loading && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No users found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
