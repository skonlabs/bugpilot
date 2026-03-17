import { useAuth } from "@/contexts/AuthContext";
import { useEffect, useState, useCallback } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Key, Copy, Check, ShieldAlert, Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

type KeyType = "live" | "test";

interface Credential {
  id: string;
  api_key: string;
  status: string;
  created_at: string;
  rotated_at: string | null;
}

function generateApiKey(type: KeyType): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const prefix = type === "live" ? "bp_live_" : "bp_test_";
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

function getKeyType(apiKey: string): KeyType {
  return apiKey.startsWith("bp_live_") ? "live" : "test";
}

export default function Credentials() {
  const { user } = useAuth();
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedType, setSelectedType] = useState<KeyType>("test");
  const [copied, setCopied] = useState("");
  const [revealedSecrets, setRevealedSecrets] = useState<Record<string, string>>({});

  const liveCred = credentials.find((c) => getKeyType(c.api_key) === "live");
  const testCred = credentials.find((c) => getKeyType(c.api_key) === "test");
  const canGenerateLive = !liveCred;
  const canGenerateTest = !testCred;

  const fetchCredentials = useCallback(async () => {
    if (!user) return;
    const { data } = await supabase
      .from("bugpilot_credentials")
      .select("*")
      .eq("user_id", user.id)
      .eq("status", "active")
      .order("created_at", { ascending: false });
    setCredentials((data as Credential[]) ?? []);
    setLoading(false);
  }, [user]);

  useEffect(() => {
    fetchCredentials();
  }, [fetchCredentials]);

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    toast.success(`${label} copied`);
    setTimeout(() => setCopied(""), 2000);
  };

  const handleGenerate = async () => {
    if (!user) return;
    if (selectedType === "live" && !canGenerateLive) {
      toast.error("You already have an active Live key. Delete it first to generate a new one.");
      return;
    }
    if (selectedType === "test" && !canGenerateTest) {
      toast.error("You already have an active Test key. Delete it first to generate a new one.");
      return;
    }

    setGenerating(true);
    try {
      const apiKey = generateApiKey(selectedType);
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

      setRevealedSecrets((prev) => ({ ...prev, [data.id]: secret }));
      await fetchCredentials();
      toast.success(`${selectedType === "live" ? "Live" : "Test"} API credentials generated`);
    } catch (err: any) {
      toast.error(err.message || "Failed to generate credentials");
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async (credId: string) => {
    try {
      const { error } = await supabase
        .from("bugpilot_credentials")
        .update({ status: "revoked", revoked_at: new Date().toISOString() })
        .eq("id", credId);

      if (error) throw error;

      setRevealedSecrets((prev) => {
        const next = { ...prev };
        delete next[credId];
        return next;
      });
      await fetchCredentials();
      toast.success("Credential deleted");
    } catch (err: any) {
      toast.error(err.message || "Failed to delete credential");
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
          Manage your BugPilot CLI activation credentials. You can have one Live and one Test key.
        </p>
      </div>

      {/* Generate section */}
      {(canGenerateLive || canGenerateTest) && (
        <div className="rounded-xl border p-6 space-y-5">
          <div className="flex items-center gap-3">
            <Plus className="h-5 w-5 text-muted-foreground" />
            <h3 className="font-semibold">Generate New Key</h3>
          </div>
          <RadioGroup
            value={selectedType}
            onValueChange={(v) => setSelectedType(v as KeyType)}
            className="flex gap-6"
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem value="test" id="type-test" disabled={!canGenerateTest} />
              <Label htmlFor="type-test" className={!canGenerateTest ? "text-muted-foreground/50 cursor-not-allowed" : ""}>
                Test Key
                <span className="ml-1.5 text-xs text-muted-foreground font-normal">
                  (bp_test_…)
                </span>
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="live" id="type-live" disabled={!canGenerateLive} />
              <Label htmlFor="type-live" className={!canGenerateLive ? "text-muted-foreground/50 cursor-not-allowed" : ""}>
                Live Key
                <span className="ml-1.5 text-xs text-muted-foreground font-normal">
                  (bp_live_…)
                </span>
              </Label>
            </div>
          </RadioGroup>
          <Button
            onClick={handleGenerate}
            disabled={generating || (selectedType === "live" && !canGenerateLive) || (selectedType === "test" && !canGenerateTest)}
          >
            {generating ? "Generating…" : `Generate ${selectedType === "live" ? "Live" : "Test"} Key`}
          </Button>
        </div>
      )}

      {/* Credential cards */}
      {[testCred, liveCred].filter(Boolean).map((cred) => {
        const type = getKeyType(cred!.api_key);
        const secret = revealedSecrets[cred!.id];
        return (
          <CredentialCard
            key={cred!.id}
            cred={cred!}
            type={type}
            revealedSecret={secret}
            copied={copied}
            onCopy={copyText}
            onRevoke={handleRevoke}
          />
        );
      })}

      {credentials.length === 0 && !canGenerateLive && !canGenerateTest && (
        <div className="rounded-xl border p-8 text-center">
          <Key className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">No active credentials.</p>
        </div>
      )}
    </div>
  );
}

function CredentialCard({
  cred,
  type,
  revealedSecret,
  copied,
  onCopy,
  onRevoke,
}: {
  cred: Credential;
  type: KeyType;
  revealedSecret?: string;
  copied: string;
  onCopy: (text: string, label: string) => void;
  onRevoke: (id: string) => void;
}) {
  const label = type === "live" ? "Live" : "Test";
  const badgeClass =
    type === "live"
      ? "bg-success/10 text-success"
      : "bg-warning/10 text-warning";

  return (
    <div className="rounded-xl border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${badgeClass}`}>
            {label}
          </span>
          <span className="text-xs text-muted-foreground">Active</span>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive">
              <Trash2 className="h-4 w-4" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete {label} Key?</AlertDialogTitle>
              <AlertDialogDescription>
                This will revoke the key immediately. Any CLI instances using it will stop working.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => onRevoke(cred.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      {revealedSecret && (
        <div className="rounded-lg border border-warning bg-warning/5 p-4 space-y-2">
          <div className="flex items-start gap-2">
            <ShieldAlert className="h-4 w-4 text-warning mt-0.5 shrink-0" />
            <p className="text-sm font-medium">Copy your secret now — it won't be shown again</p>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded-md border bg-secondary px-3 py-2 font-mono text-sm break-all">
              {revealedSecret}
            </code>
            <Button variant="ghost" size="icon" onClick={() => onCopy(revealedSecret, `${label} Secret`)}>
              {copied === `${label} Secret` ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      )}

      <div>
        <span className="text-sm font-medium">API Key</span>
        <div className="mt-1 flex items-center gap-2">
          <code className="flex-1 rounded-md border bg-secondary px-3 py-2 font-mono text-sm break-all">
            {cred.api_key}
          </code>
          <Button variant="ghost" size="icon" onClick={() => onCopy(cred.api_key, `${label} Key`)}>
            {copied === `${label} Key` ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <div>
        <span className="text-sm font-medium">Secret</span>
        <div className="mt-1 rounded-md border bg-secondary px-3 py-2 text-sm text-muted-foreground">
          ••••••••••••••••••••••••
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Secret is shown only at generation time.
        </p>
      </div>

      <div className="text-sm">
        <span className="text-muted-foreground">Created</span>
        <p className="font-medium">{new Date(cred.created_at).toLocaleDateString()}</p>
      </div>

      <div className="rounded-lg border bg-info/5 p-4 text-sm">
        <p className="font-medium">Activate the CLI</p>
        <code className="mt-2 block rounded bg-foreground px-3 py-2 font-mono text-xs text-primary-foreground">
          bugpilot auth activate --key {cred.api_key} --secret YOUR_SECRET
        </code>
      </div>
    </div>
  );
}
