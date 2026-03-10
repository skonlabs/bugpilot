// Force GitHub sync
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, Terminal, Search, Zap, Shield, GitBranch, BarChart3 } from "lucide-react";
import { motion } from "framer-motion";

const features = [
  { icon: Terminal, title: "CLI-First", description: "Investigate production issues directly from your terminal. No context switching." },
  { icon: Search, title: "Intelligent Tracing", description: "Automatically trace errors through your stack to find root causes fast." },
  { icon: Zap, title: "Instant Analysis", description: "Get actionable insights in seconds, not hours of manual log combing." },
  { icon: Shield, title: "Secure by Default", description: "API key authentication, encrypted connections, and audit trails built-in." },
  { icon: GitBranch, title: "Connector Ecosystem", description: "Integrate with GitHub, Sentry, Datadog, PagerDuty, and more." },
  { icon: BarChart3, title: "Investigation History", description: "Track and share past investigations. Build a searchable knowledge base." },
];

export default function Index() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="container relative z-10 py-24 lg:py-36">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mx-auto max-w-3xl text-center"
          >
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border bg-secondary px-4 py-1.5 text-sm font-medium text-muted-foreground">
              <Terminal className="h-3.5 w-3.5" />
              CLI-first debugging platform
            </div>
            <h1 className="text-balance text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
              AI That Finds the Root Cause of{" "}
              <span className="text-primary">Production Incidents</span>
            </h1>
            <p className="mx-auto mt-6 max-w-xl text-lg text-muted-foreground">
              BugPilot is an AI-powered CLI that analyzes logs, metrics, traces, deployments, and code changes to identify the most likely cause of an issue — and help engineers resolve it faster.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Button size="lg" asChild>
                <Link to="/sign-up">
                  Get Started Free <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to="/docs">Read the Docs</Link>
              </Button>
            </div>
          </motion.div>

          {/* Terminal mockup */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mx-auto mt-16 max-w-3xl"
          >
            <div className="overflow-hidden rounded-xl border bg-foreground shadow-2xl">
              <div className="flex items-center gap-2 border-b border-muted-foreground/20 px-4 py-3">
                <div className="h-3 w-3 rounded-full bg-destructive/60" />
                <div className="h-3 w-3 rounded-full bg-warning/60" />
                <div className="h-3 w-3 rounded-full bg-success/60" />
                <span className="ml-2 text-xs text-primary-foreground/50 font-mono">Terminal</span>
              </div>
              <div className="p-5 font-mono text-sm leading-relaxed text-primary-foreground/90">
                <div><span className="text-success">$</span> bugpilot investigate --trace ERR-4829</div>
                <div className="mt-2 text-primary-foreground/50">⠋ Tracing error through 12 services...</div>
                <div className="mt-1 text-primary-foreground/50">✓ Root cause identified in 2.3s</div>
                <div className="mt-3"><span className="text-warning">→</span> NullPointerException at UserService.java:142</div>
                <div className="text-primary-foreground/50">  Caused by: missing null check on user.preferences</div>
                <div className="text-primary-foreground/50">  First seen: 2h ago | Affected: 847 requests</div>
                <div className="mt-3"><span className="text-success">$</span> bugpilot fix --suggest</div>
                <div className="mt-1 text-primary-foreground/50">✓ 3 fix suggestions generated</div>
              </div>
            </div>
          </motion.div>
        </div>
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-primary/5 via-transparent to-transparent" />
      </section>

      {/* Features */}
      <section className="border-t bg-secondary/30 py-24">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight">Everything you need to debug at speed</h2>
            <p className="mt-4 text-muted-foreground">Purpose-built tools that integrate directly into your engineering workflow.</p>
          </div>
          <div className="mx-auto mt-16 grid max-w-5xl gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-xl border bg-card p-6"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{f.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="container">
          <div className="mx-auto max-w-2xl rounded-2xl border bg-primary/5 p-10 text-center">
            <h2 className="text-2xl font-bold">Ready to debug smarter?</h2>
            <p className="mt-3 text-muted-foreground">Create your account, download the CLI, and start investigating in minutes.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Button size="lg" asChild>
                <Link to="/sign-up">Create Free Account</Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to="/download">Download CLI</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
