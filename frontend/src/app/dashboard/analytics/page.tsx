import { api } from "@/lib/api";

export default async function AnalyticsPage() {
  let installations: any[] = [];
  let insights: any[] = [];

  try {
    const data = await api.listInstallations();
    installations = data.installations;

    if (installations.length > 0) {
      const insightData = await api.getInsights(
        installations[0].installation_id
      );
      insights = insightData.insights;
    }
  } catch {
    // Backend not connected
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Analytics</h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {["7d", "30d", "90d"].map((window) => {
          const insight = insights.find((i: any) => i.window === window);
          return (
            <div
              key={window}
              className="rounded-lg border border-border bg-card p-6"
            >
              <h3 className="text-sm font-medium uppercase text-muted-foreground">
                {window}
              </h3>
              <div className="mt-4 space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">
                    Total Findings
                  </span>
                  <span className="font-bold">
                    {insight?.total_findings ?? "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">
                    Disputed
                  </span>
                  <span className="font-bold text-yellow-500">
                    {insight?.disputed_findings ?? "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">
                    Resolved
                  </span>
                  <span className="font-bold text-green-500">
                    {insight?.resolved_findings ?? "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">
                    Quiet Drops
                  </span>
                  <span className="font-bold text-red-500">
                    {insight?.quiet_drops ?? "—"}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-6 py-4">
          <h3 className="text-lg font-semibold">Connected Repositories</h3>
        </div>
        {installations.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            No installations found. Install the GitHub App to get started.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {installations.map((inst: any) => (
              <div
                key={`${inst.installation_id}-${inst.repo_full_name}`}
                className="flex items-center justify-between px-6 py-4"
              >
                <div>
                  <p className="font-medium">{inst.repo_full_name}</p>
                  <p className="text-sm text-muted-foreground">
                    Installation #{inst.installation_id}
                  </p>
                </div>
                <span className="text-sm text-muted-foreground">
                  {inst.model_id || "default model"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
