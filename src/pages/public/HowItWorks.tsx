import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

const steps = [
  { step: "01", title: "Create an Account", desc: "Sign up for BugPilot. Your admin will issue API credentials for CLI activation." },
  { step: "02", title: "Download the CLI", desc: "Download the BugPilot CLI for macOS or Windows from your dashboard." },
  { step: "03", title: "Activate with Credentials", desc: "Run `bugpilot activate` with your API key and secret to authenticate the CLI." },
  { step: "04", title: "Investigate Issues", desc: "Use `bugpilot investigate` to trace errors, analyze root causes, and resolve incidents." },
  { step: "05", title: "Connect Your Stack", desc: "Set up connectors to enrich investigations with data from GitHub, Sentry, and more." },
];

export default function HowItWorks() {
  return (
    <div className="py-20">
      <div className="container">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl font-extrabold tracking-tight">How BugPilot Works</h1>
          <p className="mt-4 text-lg text-muted-foreground">From sign-up to resolution in five simple steps.</p>
        </div>
        <div className="mx-auto mt-20 max-w-2xl space-y-12">
          {steps.map((s) => (
            <div key={s.step} className="flex gap-6">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 border-primary text-lg font-bold text-primary">
                {s.step}
              </div>
              <div>
                <h3 className="text-lg font-semibold">{s.title}</h3>
                <p className="mt-1 text-muted-foreground">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-16 text-center">
          <Button size="lg" asChild>
            <Link to="/sign-up">Get Started <ArrowRight className="ml-2 h-4 w-4" /></Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
