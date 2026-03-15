import { Outlet, Link, useLocation, useParams } from "react-router-dom";
import { useState, useMemo } from "react";
import { Bug, Search, Menu, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { docsCategories, docsPages } from "@/data/docs";
import { cn } from "@/lib/utils";

export default function DocsLayout() {
  const [search, setSearch] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const currentSlug = location.pathname.replace("/docs/", "").replace("/docs", "") || "introduction";

  const filteredCategories = useMemo(() => {
    if (!search) return docsCategories;
    const q = search.toLowerCase();
    return docsCategories.map((cat) => ({
      ...cat,
      items: cat.items.filter((slug) => {
        const page = docsPages[slug];
        return page && (page.title.toLowerCase().includes(q) || page.content.toLowerCase().includes(q));
      }),
    })).filter((cat) => cat.items.length > 0);
  }, [search]);

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search docs..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 text-sm" />
        </div>
      </div>
      <nav className="flex-1 overflow-auto px-3 pb-4">
        {filteredCategories.map((cat) => (
          <div key={cat.label} className="mb-4">
            <div className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{cat.label}</div>
            <div className="ml-3 border-l border-border pl-1">
              {cat.items.map((slug) => {
                const page = docsPages[slug];
                if (!page) return null;
                return (
                  <Link
                    key={slug}
                    to={`/docs/${slug}`}
                    onClick={() => setSidebarOpen(false)}
                    className={cn(
                      "block rounded-md px-3 py-1.5 text-sm transition-colors",
                      currentSlug === slug ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    {page.title}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </div>
  );

  return (
    <div className="flex min-h-screen flex-col">
      {/* Top nav */}
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-lg">
        <div className="flex h-14 items-center gap-4 px-4 lg:px-6">
          <Link to="/" className="flex items-center gap-2 font-bold">
            <Bug className="h-5 w-5 text-primary" />
            <span>BugPilot</span>
          </Link>
          <span className="text-sm text-muted-foreground">/</span>
          <span className="text-sm font-medium">Docs</span>
          <div className="flex-1" />
          <Link to="/sign-in" className="text-sm text-muted-foreground hover:text-foreground">Sign In</Link>
          <button className="md:hidden" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </header>

      <div className="flex flex-1">
        {/* Desktop sidebar */}
        <aside className="hidden w-64 shrink-0 border-r md:block">
          <div className="sticky top-14 h-[calc(100vh-3.5rem)] overflow-auto">
            {sidebar}
          </div>
        </aside>

        {/* Mobile sidebar */}
        {sidebarOpen && (
          <div className="fixed inset-0 top-14 z-40 bg-background md:hidden">
            {sidebar}
          </div>
        )}

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <div className="mx-auto max-w-3xl px-6 py-10">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
