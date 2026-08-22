import Link from "next/link";
import { api } from "@/lib/api";
import { formatDate, scoreColor } from "@/lib/utils";

export default async function ReviewsPage({
  searchParams,
}: {
  searchParams: { repo?: string; status?: string };
}) {
  let reviews: any[] = [];
  let total = 0;

  try {
    const data = await api.listReviews({
      repo: searchParams.repo,
      status: searchParams.status,
      limit: 100,
    });
    reviews = data.reviews;
    total = data.total;
  } catch {
    // Backend not connected
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">All Reviews ({total})</h2>
        <div className="flex gap-2">
          <select
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm"
            defaultValue={searchParams.status || ""}
          >
            <option value="">All statuses</option>
            <option value="complete">Complete</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card">
        {reviews.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            No reviews found.
          </div>
        ) : (
          <table className="w-full">
            <thead className="border-b border-border">
              <tr className="text-left text-sm text-muted-foreground">
                <th className="px-6 py-3 font-medium">Score</th>
                <th className="px-6 py-3 font-medium">Repository</th>
                <th className="px-6 py-3 font-medium">PR</th>
                <th className="px-6 py-3 font-medium">Findings</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {reviews.map((review) => (
                <tr key={review.id} className="hover:bg-accent/50">
                  <td className="px-6 py-4">
                    <span
                      className={`text-lg font-bold ${scoreColor(
                        review.merge_score || 0
                      )}`}
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
