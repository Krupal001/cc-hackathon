"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatDate, scoreColor } from "@/lib/utils";
import { Loader2, RefreshCw, AlertTriangle } from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";

export default function ReviewsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [reviews, setReviews] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const statusFilter = searchParams.get("status") || "";
  const repoFilter = searchParams.get("repo") || "";

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await api.listReviews({
        repo: repoFilter || undefined,
        status: statusFilter || undefined,
        limit: 100,
      });
      setReviews(data.reviews);
      setTotal(data.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`API error: ${msg}`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [repoFilter, statusFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStatusChange = (value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set("status", value);
    else params.delete("status");
    router.push(`/dashboard/reviews?${params.toString()}`);
  };

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
        <h2 className="text-xl font-semibold">All Reviews ({total})</h2>
        <div className="flex gap-2">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <select
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm"
            value={statusFilter}
            onChange={(e) => handleStatusChange(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="complete">Complete</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-yellow-500" />
          <p className="text-sm text-yellow-500">{error}</p>
        </div>
      )}

      <div className="rounded-lg border border-border bg-card">
        {reviews.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-muted-foreground">No reviews found.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Open a PR in a connected repository to trigger a review.
            </p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="border-b border-border">
              <tr className="text-left text-sm text-muted-foreground">
                <th className="px-6 py-3 font-medium">Score</th>
                <th className="px-6 py-3 font-medium">Repository</th>
                <th className="px-6 py-3 font-medium">PR</th>
                <th className="px-6 py-3 font-medium">Findings</th>
                <th className="px-6 py-3 font-medium">Tokens</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {reviews.map((review) => (
                <tr
                  key={review.id}
                  onClick={() => router.push(`/dashboard/reviews/${review.id}`)}
                  className="cursor-pointer hover:bg-accent/50"
                >
                  <td className="px-6 py-4">
                    <span
                      className={`text-lg font-bold ${scoreColor(review.merge_score || 0)}`}
                    >
                      {review.merge_score || "—"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm font-medium">
                    {review.repo_full_name}
                  </td>
                  <td className="px-6 py-4 text-sm">#{review.pr_number}</td>
                  <td className="px-6 py-4 text-sm">
                    {review.findings?.length || 0}
                  </td>
                  <td className="px-6 py-4 text-sm text-muted-foreground">
                    {(() => {
                      const total = (review.input_tokens || 0) + (review.output_tokens || 0);
                      if (!total) return "—";
                      return (
                        <span title={`↑${(review.input_tokens||0).toLocaleString()} in / ↓${(review.output_tokens||0).toLocaleString()} out`}>
                          {total >= 1000 ? `${(total / 1000).toFixed(1)}k` : total}
                        </span>
                      );
                    })()}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-medium ${
                        review.status === "complete"
                          ? "bg-green-500/10 text-green-500"
                          : review.status === "failed"
                            ? "bg-red-500/10 text-red-500"
                            : "bg-yellow-500/10 text-yellow-500"
                      }`}
                    >
                      {review.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-muted-foreground">
                    {formatDate(review.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
