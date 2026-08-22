"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { Loader2, RefreshCw, AlertTriangle, Search, ExternalLink, GitBranch, Clock } from "lucide-react";

interface Repository {
  installation_id: number;
  repo_full_name: string;
  model_id: string | null;
  reviewCount?: number;
  lastReviewedAt?: string | null;
}

export default function RepositoriesPage() {
  const [installations, setInstallations] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await api.listInstallations();
      
      // Fetch review counts for each repo
      const reposWithStats = await Promise.all(
        data.installations.map(async (inst: Repository) => {
          try {
            const reviews = await api.listReviews({ 
              repo: inst.repo_full_name,
              limit: 1 
            });
            return {
              ...inst,
              reviewCount: reviews.total || 0,
              lastReviewedAt: reviews.reviews[0]?.created_at || null,
            };
          } catch {
            return { ...inst, reviewCount: 0, lastReviewedAt: null };
          }
        })
      );
      
      setInstallations(reposWithStats);
    } catch (err) {
      setError("Failed to load repositories. Is the backend running?");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filtered = useMemo(() => {
    let result = installations;

    if (search) {
      const q = search.toLowerCase();
      result = result.filter((r) => r.repo_full_name.toLowerCase().includes(q));
    }

    if (statusFilter === "no-reviews") {
      result = result.filter((r) => (r.reviewCount || 0) === 0);
    }

    return result;
  }, [installations, search, statusFilter]);

  const clearFilters = useCallback(() => {
    setSearch("");
    setStatusFilter("all");
  }, []);

  const hasFilters = search || statusFilter !== "all";

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
        <div>
          <h2 className="text-xl font-semibold">Repositories</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            All repositories with CodeSentinel installed.
          </p>
        </div>
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

      <div className="flex items-center gap-6 rounded-lg border border-border bg-card px-6 py-4">
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-bold tabular-nums">
            {installations.length}
          </span>
          <span className="text-sm text-muted-foreground">connected</span>
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            type="text"
            placeholder="Search repos..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-52 rounded-md border border-border bg-card py-1.5 pl-8 pr-3 text-sm placeholder-muted-foreground focus:border-primary focus:outline-none"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
        >
          <option value="all">All</option>
          <option value="no-reviews">No reviews yet</option>
        </select>
      </div>

      {installations.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-card py-24 text-center">
          <GitBranch className="mb-4 h-8 w-8 text-muted-foreground" />
          <div className="text-sm font-medium">No repositories connected</div>
          <div className="mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground">
            CodeSentinel doesn&apos;t have access to any repositories yet.
            Configure the GitHub App installation to select repos.
          </div>
          <a
            href={
              process.env.NEXT_PUBLIC_GITHUB_APP_URL ||
              "https://github.com/apps/review-x/installations/new"
            }
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-sm transition-colors hover:bg-accent"
          >
            Configure on GitHub <ExternalLink size={12} />
          </a>
        </div>
      ) : filtered.length === 0 && hasFilters ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-card py-24 text-center">
          <Search className="mb-4 h-7 w-7 text-muted-foreground" />
          <div className="text-sm font-medium">No repos match your filters</div>
          <button
            onClick={clearFilters}
            className="mt-3 text-xs text-primary hover:underline"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((repo) => (
            <RepoCard key={`${repo.installation_id}-${repo.repo_full_name}`} repo={repo} />
          ))}
        </div>
      )}
    </div>
  );
}

function RepoCard({ repo }: { repo: Repository }) {
  const githubUrl = `https://github.com/${repo.repo_full_name}`;
  const reviewCount = repo.reviewCount || 0;

  return (
    <div className="rounded-lg border border-border bg-card p-5 transition-colors hover:border-primary/50">
      <div className="mb-3 flex items-start justify-between">
        <div className="min-w-0">
          <a
            href={githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-1.5 text-sm font-medium transition-colors hover:text-primary"
          >
            {repo.repo_full_name}
            <ExternalLink
              size={11}
              className="text-muted-foreground transition-colors group-hover:text-primary"
            />
          </a>
          <div className="mt-1 flex items-center gap-2">
            {repo.model_id && (
              <span className="text-xs text-muted-foreground">{repo.model_id}</span>
            )}
            <span className="text-xs text-muted-foreground">
              Installation #{repo.installation_id}
            </span>
          </div>
        </div>
      </div>

      <div className="mb-3 border-t border-border/50" />

      {reviewCount === 0 ? (
        <div className="flex items-center gap-2 py-1">
          <Clock size={13} className="text-muted-foreground" />
          <span className="text-xs text-muted-foreground">
            No reviews yet — open a PR to trigger the first one.
          </span>
        </div>
      ) : (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Reviews</span>
            <span className="text-xs font-medium tabular-nums">{reviewCount}</span>
          </div>
          {repo.lastReviewedAt && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Last review</span>
              <span className="text-xs text-muted-foreground">
                {new Date(repo.lastReviewedAt).toLocaleDateString()}
              </span>
            </div>
          )}
          <div className="mt-2 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
            <span className="text-xs text-green-500">Active</span>
          </div>
        </div>
      )}
    </div>
  );
}
