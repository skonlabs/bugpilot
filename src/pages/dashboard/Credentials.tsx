import { useAuth } from "@/contexts/AuthContext";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Key, Copy, Check, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

function generateApiKey(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const prefix = "bp_";
  let key = "";
  for (let i = 0; i < 32; i++) {
    key += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return prefix + key;
}

function generateSecret(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
  let secret = "";
  for (let i = 0; i < 48; i++) {
    secret += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return secret;
}

async function hashSecret(secret: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(secret);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export default function Credentials() {
  const { user } = useAuth();
  const [cred, setCred] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState("");
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      supabase
        .from("bugpilot_credentials")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false })
        .limit(1)
        .then(({ data }) => {
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

  const handleGenerate = async () => {
    if (!user) return;
    setGenerating(true);

    try {
      const apiKey = generateApiKey();
      const secret = generateSecret();
      const secretHash = await hashSecret(secret);

      const { data, error } = await supabase
        .from("bugpilot_credentials")
        .insert({
          user_id: user.id,
          api_key: apiKey,
          secret_hash: secretHash,
          status: "active",
          created_by: user.id,
        })
        .select()
        .single();

      if (error) throw error;

      setCred(data);
      setRevealedSecret(secret);
      toast.success("API credentials generated successfully");
    } catch (err: any) {
      toast.error(err.message || "Failed to generate credentials");
    } finally {
      setGenerating(false);
    }
  };

  if (loading)
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">API Credentials</h1>
        <p className="mt-1 text-muted-foreground">
          Your BugPilot CLI activation credentials.
        </p>
      </div>

      {!cred ? (
        <div className="rounded-xl border p-8 text-center space-y-4">
          <Key className="mx-auto h-10 w-10 text-muted-foreground" />
          <h3 className="font-semibold">No credentials yet</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Generate your API key and secret to activate the BugPilot CLI. The
            secret will only be shown once — make sure to copy it.
          </p>
          <Button onClick={handleGenerate} disabled={generating}>
            {generating ? "Generating…" : "Generate API Credentials"}
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {revealedSecret && (
            <div className="rounded-xl border border-warning bg-warning/5 p-5 space-y-3">
              <div className="flex items-start gap-3">
                <ShieldAlert className="h-5 w-5 text-warning mt-0.5 shrink-0" />
                <div className="space-y-1">
                  <p className="font-semibold text-sm">
                    Copy your secret now — it won't be shown again
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Store it securely. If you lose it, you'll need to contact
                    your admin to rotate credentials.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded-md border bg-secondary px-3 py-2 font-mono text-sm break-all">
                  {revealedSecret}
                </code>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => copyText(revealedSecret, "Secret")}
                >
                  {copied === "Secret" ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          )}

          <div className="rounded-xl border p-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Status</span>
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  cred.status === "active"
                    ? "bg-success/10 text-success"
                    : "bg-destructive/10 text-destructive"
                }`}
              >
                {cred.status}
              </span>
            </div>
            <div>
              <span className="text-sm font-medium">API Key</span>
              <div className="mt-1 flex items-center gap-2">
                <code className="flex-1 rounded-md border bg-secondary px-3 py-2 font-mono text-sm break-all">
                  {cred.api_key}
                </code>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => copyText(cred.api_key, "API Key")}
                >
                  {copied === "API Key" ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
            <div>
              <span className="text-sm font-medium">Secret</span>
              <div className="mt-1 rounded-md border bg-secondary px-3 py-2 text-sm text-muted-foreground">
                ••••••••••••••••••••••••
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Secret is shown only at generation time. Contact your admin to
                rotate if needed.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Created</span>
                <p className="font-medium">
                  {new Date(cred.created_at).toLocaleDateString()}
                </p>
              </div>
              {cred.rotated_at && (
                <div>
                  <span className="text-muted-foreground">Last Rotated</span>
                  <p className="font-medium">
                    {new Date(cred.rotated_at).toLocaleDateString()}
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-lg border bg-info/5 p-4 text-sm">
            <p className="font-medium">Activate the CLI</p>
            <code className="mt-2 block rounded bg-foreground px-3 py-2 font-mono text-xs text-primary-foreground">
              bugpilot auth activate --key {cred.api_key} --secret YOUR_SECRET
            </code>
          </div>
        </div>
      )}
    </div>
  );
}
