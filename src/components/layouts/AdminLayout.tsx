import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bug, LayoutDashboard, Users, Key, ScrollText, Package, ArrowLeft, LogOut } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

const adminLinks = [
  { label: "Overview", href: "/admin", icon: LayoutDashboard },
  { label: "Users", href: "/admin/users", icon: Users },
  { label: "Credentials", href: "/admin/credentials", icon: Key },
  { label: "Audit Logs", href: "/admin/audit-logs", icon: ScrollText },
  { label: "Releases", href: "/admin/releases", icon: Package },
];

export default function AdminLayout() {
  const { signOut } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 flex-col border-r bg-sidebar lg:flex">
        <div className="flex h-16 items-center gap-2 border-b px-6">
          <Bug className="h-5 w-5 text-primary" />
          <span className="font-bold">Admin Console</span>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {adminLinks.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                (link.href === "/admin" ? location.pathname === "/admin" : location.pathname.startsWith(link.href))
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent"
              )}
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="border-t p-3 space-y-1">
          <Link to="/dashboard" className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-sidebar-accent">
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Link>
          <button onClick={async () => { await signOut(); navigate("/"); }} className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-destructive hover:bg-secondary">
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b px-6 lg:hidden">
          <Link to="/admin" className="flex items-center gap-2 font-bold">
            <Bug className="h-5 w-5 text-primary" />
            Admin
          </Link>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
