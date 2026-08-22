import { api } from "@/lib/api";
import { GitBranch, TrendingUp, AlertCircle, CheckCircle2 } from "lucide-react";
import { formatDate, scoreColor } from "@/lib/utils";

export default async function DashboardPage() {
  let reviews: any[] = [];
  let total = 0;

  try {
    const data = await api.listReviews({ limit: 10 });
    reviews = data.reviews;
    total = data.total;
  } catch {
    // Backend not connected yet
  }

  const completed = reviews.filter((r) => r.status === "complete").length;
  const failed = reviews.filter((r) => r.status === "failed").length;
  const avgScore =
    reviews.length > 0
      ? (
          reviews
            .filter((r) => r.merge_score !== null)
            .reduce((sum, r) => sum + (r.merge_score || 0), 0) /
          Math.max(1, reviews.filter((r) => r.merge_score !== null).length)
        ).toFixed(1)
      : "—";

  const stats = [
    {
      label: "Total Reviews",
      value: total,
      icon: GitBranch,
      color: "text-blue-500",
    },
    {
      label: "Completed",
      value: completed,
      icon: CheckCircle2,
      color: "text-green-500",
    },
    {
      label: "Failed",
      value: failed,
      icon: AlertCircle,
      color: "text-red-500",
    },
    {
      label: "Avg Score",
      value: avgScore,
      icon: TrendingUp,
      color: "text-yellow-500",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="rounded-lg border border-border bg-card p-6"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                  <p className="mt-2 text-2xl font-bold">{stat.value}</p>
                </div>
                <Icon className={`h-8 w-8 ${stat.color}`} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-6 py-4">
          <h2 className="text-lg font-semibold">Recent Reviews</h2>
        </div>
        {reviews.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            No reviews yet. Install the GitHub App and open a PR to get started.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {reviews.map((review) => (
              <div
                key={review.id}
                className="flex items-center justify-between px-6 py-4 hover:bg-accent/50"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold ${scoreColor(
                      review.merge_score || 0
                    )}`}
                  >
                    {review.merge_score || "—"}
                  </div>
                  <div>
                    <p className="font-medium">
                      {review.repo_full_name}#{review.pr_number}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {review.findings?.length || 0} findings ·{" "}
                      {formatDate(review.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
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
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
