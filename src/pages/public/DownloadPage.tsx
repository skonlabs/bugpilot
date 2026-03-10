import { Apple, Monitor, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

function CopyBlock({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); };
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-foreground px-4 py-3 font-mono text-sm text-primary-foreground">
      <code className="flex-1 overflow-auto">{text}</code>
      <button onClick={copy} className="shrink-0 text-primary-foreground/60 hover:text-primary-foreground">
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </button>
    </div>
  );
}

export default function DownloadPage() {
  return (
    <div className="py-20">
      <div className="container">
        <div className="mx-auto max-w-3xl">
          <h1 className="text-4xl font-extrabold tracking-tight">Download BugPilot CLI</h1>
          <p className="mt-4 text-lg text-muted-foreground">Available for macOS and Windows. Requires a BugPilot account with valid API credentials.</p>

          <div className="mt-12 grid gap-8 md:grid-cols-2">
            <div className="rounded-xl border p-6">
              <div className="flex items-center gap-3">
                <Apple className="h-8 w-8" />
                <div>
                  <h3 className="font-semibold text-lg">macOS</h3>
                  <p className="text-xs text-muted-foreground">macOS 12+ (Intel & Apple Silicon)</p>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                <p className="text-sm font-medium">Install via Homebrew:</p>
                <CopyBlock text="brew install bugpilot/tap/bugpilot" />
                <p className="text-sm font-medium mt-4">Or download directly:</p>
                <Button variant="outline" className="w-full">Download .pkg (v1.0.0)</Button>
              </div>
            </div>

            <div className="rounded-xl border p-6">
              <div className="flex items-center gap-3">
                <Monitor className="h-8 w-8" />
                <div>
                  <h3 className="font-semibold text-lg">Windows</h3>
                  <p className="text-xs text-muted-foreground">Windows 10+ (64-bit)</p>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                <p className="text-sm font-medium">Install via Scoop:</p>
                <CopyBlock text="scoop install bugpilot" />
                <p className="text-sm font-medium mt-4">Or download directly:</p>
                <Button variant="outline" className="w-full">Download .msi (v1.0.0)</Button>
              </div>
            </div>
          </div>

          <div className="mt-12 space-y-6">
            <h2 className="text-2xl font-bold">Activate the CLI</h2>
            <p className="text-muted-foreground">After installation, activate BugPilot with your license key and API secret:</p>
            <CopyBlock text="bugpilot auth activate --key bp_YOUR_LICENSE_KEY --secret YOUR_API_SECRET" />
            <div className="rounded-lg border bg-info/10 p-4 text-sm">
              <p className="font-medium text-info">Where do I find my credentials?</p>
              <p className="mt-1 text-muted-foreground">Your license key and API secret are shown under <strong>API Credentials</strong> after you log in. The secret is only displayed once at generation time — store it securely.</p>
            </div>
          </div>

          <div className="mt-12 space-y-4">
            <h2 className="text-2xl font-bold">Verify Installation</h2>
            <CopyBlock text="bugpilot --version" />
            <CopyBlock text="bugpilot auth whoami" />
          </div>
        </div>
      </div>
    </div>
  );
}
