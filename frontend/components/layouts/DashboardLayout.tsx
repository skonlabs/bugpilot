import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bug, LayoutDashboard, Download, BookOpen, Key, Settings, LogOut, Shield } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const userLinks = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Downloads", href: "/dashboard/downloads", icon: Download },
  { label: "Documentation", href: "/docs", icon: BookOpen },
  { label: "API Credentials", href: "/dashboard/credentials", icon: Key },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
];

export default function DashboardLayout() {
  const { profile, isAdmin, signOut } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate("/");
  };

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 flex-col border-r bg-sidebar lg:flex">
        <div className="flex h-16 items-center gap-2 border-b px-6">
          <Bug className="h-5 w-5 text-primary" />
          <span className="font-bold">BugPilot</span>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {userLinks.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                location.pathname === link.href
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent"
              )}
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </Link>
          ))}
          {isAdmin && (
            <>
              <div className="my-3 border-t" />
              <Link
                to="/admin"
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  location.pathname.startsWith("/admin")
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent"
                )}
              >
                <Shield className="h-4 w-4" />
                Admin Console
              </Link>
            </>
          )}
        </nav>
        <div className="border-t p-3">
          <div className="mb-2 px-3 text-xs text-muted-foreground truncate">{profile?.email}</div>
          <button onClick={handleSignOut} className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-destructive hover:bg-secondary">
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b px-6 lg:hidden">
          <Link to="/" className="flex items-center gap-2 font-bold">
            <Bug className="h-5 w-5 text-primary" />
            BugPilot
          </Link>
          <Button variant="ghost" size="sm" onClick={handleSignOut}>
            <LogOut className="h-4 w-4" />
          </Button>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
