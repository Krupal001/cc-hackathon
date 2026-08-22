import { Sidenav } from "@/components/layout/Sidenav";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <Sidenav />
      <main className="ml-64 min-h-screen">
        <div className="border-b border-border bg-card px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold">CodeSentinel Dashboard</h1>
            <div className="flex items-center gap-4">
              <span className="text-sm text-muted-foreground">
                AI-Powered Code Review
              </span>
            </div>
          </div>
        </div>
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
