import { Bug, LayoutGrid, Settings, Terminal, Activity } from "lucide-react";

const navItems = [
  { icon: Bug, label: "ANOMALIES", active: true },
  { icon: Activity, label: "TELEMETRY", active: false },
  { icon: LayoutGrid, label: "SYSTEMS", active: false },
  { icon: Terminal, label: "CONSOLE", active: false },
  { icon: Settings, label: "CONFIG", active: false },
];

export const NavigationPane = () => {
  return (
    <div className="flex h-full w-[200px] shrink-0 flex-col border-r border-border bg-background">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <Bug className="h-4 w-4 text-intercept" />
        <span className="text-xs font-semibold tracking-widest text-foreground">
          BUGPILOT
        </span>
      </div>

      {/* Nav Items */}
      <nav className="flex flex-1 flex-col py-2">
        {navItems.map((item) => (
          <button
            key={item.label}
            className={`flex items-center gap-3 px-4 py-2.5 text-[11px] tracking-wider transition-colors ${
              item.active
                ? "border-l-2 border-intercept text-foreground"
                : "border-l-2 border-transparent text-echo hover:text-foreground"
            }`}
          >
            <item.icon className="h-3.5 w-3.5" />
            {item.label}
          </button>
        ))}
      </nav>

      {/* User */}
      <div className="border-t border-border px-4 py-3">
        <span className="text-[11px] text-echo">[SYS]</span>
      </div>
    </div>
  );
};
