import { useAuth } from "@/contexts/AuthContext";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Key, Eye, EyeOff, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function Credentials() {
  const { user } = useAuth();
  const [cred, setCred] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    if (user) {
      supabase.from("bugpilot_credentials").select("*").eq("user_id", user.id).order("created_at", { ascending: false }).limit(1).then(({ data }) => {
        setCred(data?.[0] ?? null);
        setLoading(false);
      });
    }
  }, [user]);

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    toast.success(`${label} copied`);
    setTimeout(() => setCopied(""), 2000);
  };

  if (loading) return <div className="flex items-center justify-center py-20"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">API Credentials</h1>
        <p className="mt-1 text-muted-foreground">Your BugPilot CLI activation credentials.</p>
      </div>

      {!cred ? (
        <div className="rounded-xl border p-8 text-center">
          <Key className="mx-auto h-10 w-10 text-muted-foreground" />
          <h3 className="mt-4 font-semibold">No credentials issued</h3>
          <p className="mt-1 text-sm text-muted-foreground">Contact your admin to generate API credentials for your account.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-xl border p-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Status</span>
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cred.status === "active" ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"}`}>
                {cred.status}
              </span>
            </div>
            <div>
              <span className="text-sm font-medium">API Key</span>
              <div className="mt-1 flex items-center gap-2">
                <code className="flex-1 rounded-md border bg-secondary px-3 py-2 font-mono text-sm">{cred.api_key}</code>
                <Button variant="ghost" size="icon" onClick={() => copyText(cred.api_key, "API Key")}>
                  {copied === "API Key" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <div>
              <span className="text-sm font-medium">Secret</span>
              <div className="mt-1 rounded-md border bg-secondary px-3 py-2 text-sm text-muted-foreground">
                ••••••••••••••••••••••••
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Secret is shown only at generation time. Contact your admin to rotate if needed.</p>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-muted-foreground">Created</span><p className="font-medium">{new Date(cred.created_at).toLocaleDateString()}</p></div>
              {cred.rotated_at && <div><span className="text-muted-foreground">Last Rotated</span><p className="font-medium">{new Date(cred.rotated_at).toLocaleDateString()}</p></div>}
            </div>
          </div>

          <div className="rounded-lg border bg-info/5 p-4 text-sm">
            <p className="font-medium">Activate the CLI</p>
            <code className="mt-2 block rounded bg-foreground px-3 py-2 font-mono text-xs text-primary-foreground">bugpilot auth activate --key {cred.api_key} --secret YOUR_SECRET</code>
          </div>
        </div>
      )}
    </div>
  );
}
