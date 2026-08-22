"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GitBranch, Home, Settings, BarChart3, Github, Shield } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: Home },
  { label: "Reviews", href: "/dashboard/reviews", icon: GitBranch },
  { label: "Analytics", href: "/dashboard/analytics", icon: BarChart3 },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
];

export function Sidenav() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-30 h-screen w-64 border-r border-border bg-card">
      <div className="flex h-16 items-center gap-2 border-b border-border px-6">
        <Shield className="h-6 w-6 text-primary" />
        <span className="text-lg font-semibold">CodeSentinel</span>
      </div>

      <nav className="flex flex-col gap-1 p-4">
        <div className="mb-2 px-3 text-xs font-medium uppercase text-muted-foreground">
          Main
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}

        <div className="mt-6 mb-2 px-3 text-xs font-medium uppercase text-muted-foreground">
          Resources
        </div>
        <a
          href="https://github.com/CodeSewer/codesentinel"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <Github className="h-4 w-4" />
          GitHub
        </a>
      </nav>

      <div className="absolute bottom-0 left-0 right-0 border-t border-border p-4">
        <a
          href={
            process.env.NEXT_PUBLIC_GITHUB_APP_URL ||
            "https://github.com/apps/review-x/installations/new"
          }
          target="_blank"
          rel="noopener noreferrer"
          className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          <Github className="h-4 w-4" />
          Install App
        </a>
      </div>
    </aside>
  );
}
