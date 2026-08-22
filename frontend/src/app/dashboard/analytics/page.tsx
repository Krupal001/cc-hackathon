"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { Loader2, RefreshCw, AlertTriangle } from "lucide-react";

export default function AnalyticsPage() {
  const [installations, setInstallations] = useState<any[]>([]);
  const [insights, setInsights] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await api.listInstallations();
      setInstallations(data.installations);

      if (data.installations.length > 0) {
        const insightData = await api.getInsights(data.installations[0].installation_id);
        setInsights(insightData.insights);
      }
    } catch (err) {
      setError("Failed to load analytics. Is the backend running?");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Analytics</h2>
        <button
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-yellow-500" />
          <p className="text-sm text-yellow-500">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {["7d", "30d", "90d"].map((window) => {
          const insight = insights.find((i: any) => i.window === window);
          return (
            <div key={window} className="rounded-lg border border-border bg-card p-6">
              <h3 className="text-sm font-medium uppercase text-muted-foreground">
                {window}
              </h3>
              <div className="mt-4 space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Total Findings</span>
                  <span className="font-bold">{insight?.total_findings ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Disputed</span>
                  <span className="font-bold text-yellow-500">{insight?.disputed_findings ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Resolved</span>
                  <span className="font-bold text-green-500">{insight?.resolved_findings ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Quiet Drops</span>
                  <span className="font-bold text-red-500">{insight?.quiet_drops ?? "—"}</span>
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
          <div className="px-6 py-12 text-center">
            <p className="text-muted-foreground">No installations found.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Install the GitHub App to get started.
            </p>
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
