import { Link, Outlet, useLocation } from "react-router-dom";
import { useState } from "react";
import { Menu, X, Bug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

const navLinks = [
  { label: "Product", href: "/product" },
  { label: "How It Works", href: "/how-it-works" },
  { label: "Docs", href: "/docs" },
  { label: "Pricing", href: "/pricing" },
  { label: "Download", href: "/download" },
];

export default function PublicLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user } = useAuth();
  const location = useLocation();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-lg">
        <div className="container flex h-16 items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-bold text-lg">
            <Bug className="h-6 w-6 text-primary" />
            <span>BugPilot</span>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                to={link.href}
                className={cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-secondary hover:text-foreground",
                  location.pathname === link.href ? "text-foreground" : "text-muted-foreground"
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <div className="hidden items-center gap-2 md:flex">
            {user ? (
              <Button asChild size="sm">
                <Link to="/dashboard">Dashboard</Link>
              </Button>
            ) : (
              <>
                <Button variant="ghost" size="sm" asChild>
                  <Link to="/sign-in">Sign In</Link>
                </Button>
                <Button size="sm" asChild>
                  <Link to="/sign-up">Get Started</Link>
                </Button>
              </>
            )}
          </div>

          <button className="md:hidden" onClick={() => setMobileOpen(!mobileOpen)}>
            {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>

        {mobileOpen && (
          <div className="border-t bg-background p-4 md:hidden">
            <nav className="flex flex-col gap-2">
              {navLinks.map((link) => (
                <Link key={link.href} to={link.href} onClick={() => setMobileOpen(false)} className="rounded-md px-3 py-2 text-sm font-medium hover:bg-secondary">
                  {link.label}
                </Link>
              ))}
              <hr className="my-2" />
              {user ? (
                <Link to="/dashboard" onClick={() => setMobileOpen(false)} className="rounded-md px-3 py-2 text-sm font-medium text-primary">Dashboard</Link>
              ) : (
                <>
                  <Link to="/sign-in" onClick={() => setMobileOpen(false)} className="rounded-md px-3 py-2 text-sm font-medium">Sign In</Link>
                  <Link to="/sign-up" onClick={() => setMobileOpen(false)} className="rounded-md px-3 py-2 text-sm font-medium text-primary">Get Started</Link>
                </>
              )}
            </nav>
          </div>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t bg-secondary/30">
        <div className="container py-12">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Link to="/" className="flex items-center gap-2 font-bold text-lg">
                <Bug className="h-5 w-5 text-primary" />
                <span>BugPilot</span>
              </Link>
              <p className="mt-3 text-sm text-muted-foreground">CLI-first investigation and debugging platform for engineers.</p>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold">Product</h4>
              <div className="flex flex-col gap-2 text-sm text-muted-foreground">
                <Link to="/product" className="hover:text-foreground">Features</Link>
                <Link to="/how-it-works" className="hover:text-foreground">How It Works</Link>
                <Link to="/pricing" className="hover:text-foreground">Pricing</Link>
                <Link to="/download" className="hover:text-foreground">Download</Link>
              </div>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold">Resources</h4>
              <div className="flex flex-col gap-2 text-sm text-muted-foreground">
                <Link to="/docs" className="hover:text-foreground">Documentation</Link>
                <Link to="/docs/quickstart" className="hover:text-foreground">Quickstart</Link>
                <Link to="/docs/cli-commands" className="hover:text-foreground">CLI Reference</Link>
                <Link to="/docs/changelog" className="hover:text-foreground">Changelog</Link>
              </div>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold">Account</h4>
              <div className="flex flex-col gap-2 text-sm text-muted-foreground">
                <Link to="/sign-in" className="hover:text-foreground">Sign In</Link>
                <Link to="/sign-up" className="hover:text-foreground">Sign Up</Link>
              </div>
            </div>
          </div>
          <div className="mt-10 border-t pt-6 text-center text-xs text-muted-foreground">
            © {new Date().getFullYear()} BugPilot. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
