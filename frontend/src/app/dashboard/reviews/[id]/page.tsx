import { api } from "@/lib/api";
import { formatDate, severityColor, scoreColor } from "@/lib/utils";
import { ArrowLeft, GitBranch, DollarSign, Zap } from "lucide-react";
import Link from "next/link";

export default async function ReviewDetailPage({
  params,
}: {
  params: { id: string };
}) {
  let review: any = null;

  try {
    const decoded = decodeURIComponent(params.id);
    const [repoPart, prAndSha] = decoded.split(":");
    const [prNumber, commitSha] = prAndSha.split("#");
    review = await api.getReviewByKey(repoPart, parseInt(prNumber), commitSha);
  } catch {
    try {
      review = await api.getReview(parseInt(params.id));
    } catch {
      // Not found
    }
  }

  if (!review) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-lg text-muted-foreground">Review not found</p>
        <Link
          href="/dashboard/reviews"
          className="mt-4 text-primary hover:underline"
        >
          Back to reviews
        </Link>
      </div>
    );
  }

  const findings = review.findings || [];
  const criticals = findings.filter((f: any) => f.severity === "critical");
  const warnings = findings.filter((f: any) => f.severity === "warning");
  const infos = findings.filter((f: any) => f.severity === "info");

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/reviews"
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to reviews
      </Link>

      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold">
              {review.repo_full_name}#{review.pr_number}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Commit {review.commit_sha.slice(0, 8)} ·{" "}
              {formatDate(review.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div
              className={`flex h-16 w-16 items-center justify-center rounded-full text-2xl font-bold ${scoreColor(
                review.merge_score || 0
              )}`}
            >
              {review.merge_score || "—"}
            </div>
          </div>
        </div>

        {review.merge_score_reason && (
          <p className="mt-4 text-sm italic text-muted-foreground">
            {review.merge_score_reason}
          </p>
        )}

        <div className="mt-6 flex gap-6">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm">{findings.length} findings</span>
          </div>
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm">
              {review.input_tokens + review.output_tokens} tokens
            </span>
          </div>
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm">
              ${review.estimated_cost_usd.toFixed(4)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {review.enabled_agent_count} agents
            </span>
          </div>
        </div>
      </div>

      {review.summary && (
        <div className="rounded-lg border border-border bg-card p-6">
          <h3 className="mb-3 text-lg font-semibold">Summary</h3>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {review.summary}
          </p>
        </div>
      )}

      {review.diagram && review.diagram.startsWith("flowchart") && (
        <div className="rounded-lg border border-border bg-card p-6">
          <h3 className="mb-3 text-lg font-semibold">Architecture Impact</h3>
          <pre className="overflow-x-auto rounded-md bg-secondary p-4 text-xs">
            {review.diagram}
          </pre>
        </div>
      )}

      <div className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-6 py-4">
          <h3 className="text-lg font-semibold">
            Findings ({findings.length})
          </h3>
          <div className="mt-2 flex gap-4 text-sm">
            <span className="text-red-500">{criticals.length} critical</span>
            <span className="text-yellow-500">{warnings.length} warnings</span>
            <span className="text-blue-500">{infos.length} info</span>
          </div>
        </div>

        {findings.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            No findings. Clean review!
          </div>
        ) : (
          <div className="divide-y divide-border">
            {findings.map((finding: any, idx: number) => (
              <div key={idx} className="px-6 py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${severityColor(
                          finding.severity
                        )}`}
                      >
                        {finding.severity}
                      </span>
                      <span className="text-sm font-medium">
                        {finding.title}
                      </span>
                      {finding.verification && (
                        <span className="text-xs text-muted-foreground">
                          {finding.verification === "verified"
                            ? "✅ verified"
                            : "❓ unverified"}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {finding.description}
                    </p>
                    {finding.suggestion && (
                      <p className="mt-2 text-sm">
                        <span className="font-medium">Suggestion:</span>{" "}
                        {finding.suggestion}
                      </p>
                    )}
                  </div>
                  <div className="ml-4 text-right text-sm">
                    <p className="font-mono text-xs text-muted-foreground">
                      {finding.file}:{finding.line}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {finding.confidence}% confidence
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {review.error_message && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6">
          <h3 className="text-lg font-semibold text-destructive">Error</h3>
          <p className="mt-2 text-sm text-destructive">
            {review.error_message}
          </p>
        </div>
      )}
    </div>
  );
}
