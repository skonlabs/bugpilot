import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Download, Key, BookOpen, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Dashboard() {
  const { user, profile } = useAuth();
  const [hasCreds, setHasCreds] = useState(false);

  useEffect(() => {
    if (user) {
      supabase.from("bugpilot_credentials").select("id").eq("user_id", user.id).eq("status", "active").then(({ data }) => {
        setHasCreds((data?.length ?? 0) > 0);
      });
    }
  }, [user]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Welcome back{profile?.full_name ? `, ${profile.full_name}` : ""}</h1>
        <p className="mt-1 text-muted-foreground">Here's your BugPilot overview.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Link to="/dashboard/credentials" className="group rounded-xl border p-5 transition-colors hover:bg-secondary">
          <Key className={`h-8 w-8 ${hasCreds ? "text-success" : "text-warning"}`} />
          <h3 className="mt-3 font-semibold">API Credentials</h3>
          <p className="mt-1 text-sm text-muted-foreground">{hasCreds ? "Active credentials available" : "No credentials issued yet"}</p>
          <ArrowRight className="mt-3 h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1" />
        </Link>

        <Link to="/dashboard/downloads" className="group rounded-xl border p-5 transition-colors hover:bg-secondary">
          <Download className="h-8 w-8 text-primary" />
          <h3 className="mt-3 font-semibold">Download CLI</h3>
          <p className="mt-1 text-sm text-muted-foreground">Get BugPilot CLI for macOS or Windows</p>
          <ArrowRight className="mt-3 h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1" />
        </Link>

        <Link to="/docs/quickstart" className="group rounded-xl border p-5 transition-colors hover:bg-secondary">
          <BookOpen className="h-8 w-8 text-primary" />
          <h3 className="mt-3 font-semibold">Quickstart Guide</h3>
          <p className="mt-1 text-sm text-muted-foreground">Learn how to install and activate the CLI</p>
          <ArrowRight className="mt-3 h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1" />
        </Link>
      </div>

      {!hasCreds && (
        <div className="rounded-xl border border-warning/30 bg-warning/5 p-5">
          <h3 className="font-semibold text-warning">Credentials not yet issued</h3>
          <p className="mt-1 text-sm text-muted-foreground">Your admin needs to generate API credentials for your account before you can activate the CLI. Contact your team admin.</p>
        </div>
      )}

      <div className="rounded-xl border p-5">
        <h3 className="font-semibold">Getting Started</h3>
        <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex gap-2"><span className="font-medium text-foreground">1.</span> Download the BugPilot CLI for your platform</li>
          <li className="flex gap-2"><span className="font-medium text-foreground">2.</span> Get your API credentials from the Credentials page</li>
          <li className="flex gap-2"><span className="font-medium text-foreground">3.</span> Run <code className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs">bugpilot activate</code> to authenticate</li>
          <li className="flex gap-2"><span className="font-medium text-foreground">4.</span> Start investigating with <code className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs">bugpilot investigate</code></li>
        </ol>
      </div>
    </div>
  );
}
