import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";

const plans = [
  {
    name: "Starter",
    price: "Free",
    desc: "For individual developers getting started.",
    features: ["5 investigations/month", "macOS & Windows CLI", "Community support", "Basic connectors"],
    cta: "Get Started",
    primary: false,
  },
  {
    name: "Pro",
    price: "$29/mo",
    desc: "For professional engineers and small teams.",
    features: ["Unlimited investigations", "Priority support", "All connectors", "Investigation history", "Team sharing"],
    cta: "Start Pro Trial",
    primary: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    desc: "For organizations with advanced requirements.",
    features: ["Everything in Pro", "SSO & SAML", "Dedicated support", "Custom connectors", "Audit & compliance"],
    cta: "Contact Sales",
    primary: false,
  },
];

export default function Pricing() {
  return (
    <div className="py-20">
      <div className="container">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl font-extrabold tracking-tight">Simple, transparent pricing</h1>
          <p className="mt-4 text-lg text-muted-foreground">Start free. Scale as you grow.</p>
        </div>
        <div className="mx-auto mt-16 grid max-w-4xl gap-8 md:grid-cols-3">
          {plans.map((plan) => (
            <div key={plan.name} className={`rounded-xl border p-6 ${plan.primary ? "border-primary ring-2 ring-primary/20" : ""}`}>
              <h3 className="font-semibold">{plan.name}</h3>
              <div className="mt-2 text-3xl font-bold">{plan.price}</div>
              <p className="mt-1 text-sm text-muted-foreground">{plan.desc}</p>
              <ul className="mt-6 space-y-2">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm">
                    <Check className="h-4 w-4 text-success" /> {f}
                  </li>
                ))}
              </ul>
              <Button className="mt-6 w-full" variant={plan.primary ? "default" : "outline"} asChild>
                <Link to="/sign-up">{plan.cta}</Link>
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
