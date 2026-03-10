import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function AdminReleases() {
  const [releases, setReleases] = useState<any[]>([]);

  const fetchReleases = async () => {
    const { data } = await supabase.from("releases").select("*").order("created_at", { ascending: false });
    setReleases(data ?? []);
  };

  useEffect(() => { fetchReleases(); }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Release Management</h1>
        <Button variant="outline" onClick={() => toast.info("Release upload coming soon")}>Add Release</Button>
      </div>
      {releases.length === 0 ? (
        <div className="rounded-xl border p-8 text-center text-muted-foreground">
          <p>No releases published yet. Use the Supabase dashboard to upload CLI binaries and add release records.</p>
        </div>
      ) : (
        <div className="rounded-xl border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-secondary/50">
                <th className="px-4 py-3 text-left font-medium">Platform</th>
                <th className="px-4 py-3 text-left font-medium">Version</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Released</th>
              </tr>
            </thead>
            <tbody>
              {releases.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="px-4 py-3 capitalize">{r.platform}</td>
                  <td className="px-4 py-3 font-mono">{r.version}</td>
                  <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${r.status === "active" ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"}`}>{r.status}</span></td>
                  <td className="px-4 py-3 text-muted-foreground">{new Date(r.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
