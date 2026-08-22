"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { GitBranch, Home, Settings, BarChart3, Github, Shield, LogOut, FolderGit2 } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: Home },
  { label: "Reviews", href: "/dashboard/reviews", icon: GitBranch },
  { label: "Repositories", href: "/dashboard/repositories", icon: FolderGit2 },
  { label: "Analytics", href: "/dashboard/analytics", icon: BarChart3 },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
];

export function Sidenav() {
  const pathname = usePathname();
  const { data: session } = useSession();

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
        {session?.user && (
          <div className="mb-3 flex items-center gap-2 px-1">
            {session.user.image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={session.user.image}
                alt={session.user.name || "User"}
                className="h-7 w-7 rounded-full"
              />
            ) : null}
            <div className="flex-1 truncate">
              <p className="truncate text-xs font-medium">{session.user.name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {session.user.email}
              </p>
            </div>
          </div>
        )}
        <div className="flex gap-2">
          <a
            href={
              process.env.NEXT_PUBLIC_GITHUB_APP_URL ||
              "https://github.com/apps/review-x/installations/new"
            }
            target="_blank"
            rel="noopener noreferrer"
            className="flex flex-1 items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Github className="h-4 w-4" />
            Install App
          </a>
          <button
            onClick={() => signOut({ callbackUrl: "/signin" })}
            className="flex items-center justify-center rounded-md border border-border px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
