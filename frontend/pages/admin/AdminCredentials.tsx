import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Key, RotateCcw, Ban, Copy, Check, Search } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

function generateKey(prefix: string) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = prefix;
  for (let i = 0; i < 32; i++) result += chars.charAt(Math.floor(Math.random() * chars.length));
  return result;
}

async function hashSecret(secret: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(secret);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export default function AdminCredentials() {
  const { user } = useAuth();
  const [creds, setCreds] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [showGenerate, setShowGenerate] = useState(false);
  const [keyType, setKeyType] = useState<"live" | "test">("live");
  const [selectedUser, setSelectedUser] = useState("");
  const [generatedSecret, setGeneratedSecret] = useState("");
  const [generatedKey, setGeneratedKey] = useState("");
  const [copied, setCopied] = useState("");

  const fetchData = async () => {
    const [credsRes, profilesRes] = await Promise.all([
      supabase.from("bugpilot_credentials").select("*").order("created_at", { ascending: false }),
      supabase.from("profiles").select("auth_user_id, email, full_name"),
    ]);
    setCreds(credsRes.data ?? []);
    setProfiles(profilesRes.data ?? []);
  };

  useEffect(() => { fetchData(); }, []);

  const getEmail = (userId: string) => profiles.find((p) => p.auth_user_id === userId)?.email ?? userId;

  const generateCredentials = async (keyType: "live" | "test" = "live") => {
    if (!selectedUser || !user) return;
    const prefix = keyType === "live" ? "bp_live_" : "bp_test_";
    const apiKey = generateKey(prefix);
    const secret = generateKey("bps_");
    const secretHash = await hashSecret(secret);
    const { error } = await supabase.from("bugpilot_credentials").insert({
      user_id: selectedUser,
      api_key: apiKey,
      secret_hash: secretHash,
      status: "active",
      created_by: user.id,
    });
    if (error) { toast.error(error.message); return; }
    await supabase.from("audit_logs").insert({
      actor_user_id: user.id,
      target_user_id: selectedUser,
      action_type: "credential_created",
      metadata_json: { api_key: apiKey },
    });
    setGeneratedKey(apiKey);
    setGeneratedSecret(secret);
    toast.success("Credentials generated");
    fetchData();
  };

  const revokeCredential = async (credId: string, targetUserId: string) => {
    await supabase.from("bugpilot_credentials").update({ status: "revoked", revoked_at: new Date().toISOString() }).eq("id", credId);
    await supabase.from("audit_logs").insert({
      actor_user_id: user!.id,
      target_user_id: targetUserId,
      action_type: "credential_revoked",
      metadata_json: { credential_id: credId },
    });
    toast.success("Credential revoked");
    fetchData();
  };

  const rotateCredential = async (credId: string, targetUserId: string) => {
    const newSecret = generateKey("bps_");
    const newSecretHash = await hashSecret(newSecret);
    await supabase.from("bugpilot_credentials").update({ secret_hash: newSecretHash, rotated_at: new Date().toISOString() }).eq("id", credId);
    await supabase.from("audit_logs").insert({
      actor_user_id: user!.id,
      target_user_id: targetUserId,
      action_type: "credential_rotated",
      metadata_json: { credential_id: credId },
    });
    setGeneratedSecret(newSecret);
    setGeneratedKey(creds.find((c) => c.id === credId)?.api_key ?? "");
    setShowGenerate(false);
    toast.success("Secret rotated. Copy the new secret now — it won't be shown again.");
    fetchData();
  };

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 2000);
  };

  const filteredCreds = creds.filter((c) => getEmail(c.user_id).toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Credential Management</h1>
        <Button onClick={() => { setShowGenerate(true); setGeneratedSecret(""); setGeneratedKey(""); setSelectedUser(""); }}>
          <Key className="mr-2 h-4 w-4" /> Generate Credentials
        </Button>
      </div>

      {generatedSecret && (
        <div className="rounded-xl border border-warning/50 bg-warning/5 p-5 space-y-3">
          <p className="font-semibold text-warning">⚠ Save this secret now — it won't be shown again</p>
          <div>
            <p className="text-xs text-muted-foreground">API Key</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded border bg-secondary px-2 py-1 font-mono text-xs">{generatedKey}</code>
              <button onClick={() => copyText(generatedKey, "key")}>{copied === "key" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</button>
            </div>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Secret</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded border bg-secondary px-2 py-1 font-mono text-xs">{generatedSecret}</code>
              <button onClick={() => copyText(generatedSecret, "secret")}>{copied === "secret" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</button>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => setGeneratedSecret("")}>Dismiss</Button>
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search by email..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
      </div>

      <div className="rounded-xl border overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-secondary/50">
              <th className="px-4 py-3 text-left font-medium">User</th>
              <th className="px-4 py-3 text-left font-medium">API Key</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-left font-medium">Created</th>
              <th className="px-4 py-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredCreds.map((c) => (
              <tr key={c.id} className="border-b last:border-0">
                <td className="px-4 py-3 text-xs">{getEmail(c.user_id)}</td>
                <td className="px-4 py-3 font-mono text-xs">{c.api_key}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${c.status === "active" ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"}`}>{c.status}</span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{new Date(c.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-right space-x-1">
                  {c.status === "active" && (
                    <>
                      <Button variant="ghost" size="sm" onClick={() => rotateCredential(c.id, c.user_id)}><RotateCcw className="h-3 w-3 mr-1" />Rotate</Button>
                      <Button variant="ghost" size="sm" className="text-destructive" onClick={() => revokeCredential(c.id, c.user_id)}><Ban className="h-3 w-3 mr-1" />Revoke</Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={showGenerate} onOpenChange={setShowGenerate}>
        <DialogContent>
          <DialogHeader><DialogTitle>Generate API Credentials</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Select a user to generate credentials for:</p>
            <select className="w-full rounded-md border bg-background px-3 py-2 text-sm" value={selectedUser} onChange={(e) => setSelectedUser(e.target.value)}>
              <option value="">Select user...</option>
              {profiles.map((p) => <option key={p.auth_user_id} value={p.auth_user_id}>{p.email}</option>)}
            </select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowGenerate(false)}>Cancel</Button>
            <Button onClick={() => { generateCredentials(); setShowGenerate(false); }} disabled={!selectedUser}>Generate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
