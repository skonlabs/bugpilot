import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Terminal, Search, Zap, Shield, GitBranch, BarChart3, ArrowRight } from "lucide-react";

const features = [
  { icon: Terminal, title: "CLI-Native Investigation", desc: "Run investigations directly from your terminal. BugPilot fits into your existing workflow — no browser dashboards required." },
  { icon: Search, title: "Distributed Tracing", desc: "Automatically trace errors across microservices, finding the root cause through layers of complexity." },
  { icon: Zap, title: "Automated Root Cause Analysis", desc: "BugPilot analyzes logs, traces, and metrics to surface actionable root causes in seconds." },
  { icon: Shield, title: "Secure Credential System", desc: "API key + secret authentication. Credentials are issued by admins, hashed at rest, and audited." },
  { icon: GitBranch, title: "Connector Ecosystem", desc: "Plug into GitHub, Sentry, Datadog, PagerDuty, Slack, and more to enrich your investigations." },
  { icon: BarChart3, title: "Investigation History", desc: "Every investigation is logged and searchable. Build institutional debugging knowledge over time." },
];

export default function Product() {
  return (
    <div className="py-20">
      <div className="container">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl font-extrabold tracking-tight">Built for engineers who debug in the terminal</h1>
          <p className="mt-4 text-lg text-muted-foreground">BugPilot combines CLI ergonomics with intelligent analysis to help you resolve production issues faster than ever.</p>
        </div>
        <div className="mx-auto mt-20 grid max-w-5xl gap-12 md:grid-cols-2">
          {features.map((f) => (
            <div key={f.title} className="flex gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <f.icon className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold">{f.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-20 text-center">
          <Button size="lg" asChild>
            <Link to="/sign-up">Start Free <ArrowRight className="ml-2 h-4 w-4" /></Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
