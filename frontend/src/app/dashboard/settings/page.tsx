import { api } from "@/lib/api";

export default async function SettingsPage() {
  let installations: any[] = [];

  try {
    const data = await api.listInstallations();
    installations = data.installations;
  } catch {
    // Backend not connected
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Settings</h2>

      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="text-lg font-semibold">GitHub App</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Manage your GitHub App installation and review configuration.
        </p>
        <a
          href={
            process.env.NEXT_PUBLIC_GITHUB_APP_URL ||
            "https://github.com/apps/code-sentinal/installations/new"
          }
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Configure on GitHub
        </a>
      </div>

      <div className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-6 py-4">
          <h3 className="text-lg font-semibold">Connected Repositories</h3>
        </div>
        {installations.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            No repositories connected. Install the GitHub App to get started.
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
                <div className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground">
                    {inst.model_id || "default model"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="text-lg font-semibold">Review Configuration</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Default review settings applied to all repositories. Individual repos
          can override these via <code className="text-xs">.codesentinel.yml</code>.
        </p>
        <div className="mt-4 space-y-4">
          <div>
            <label className="text-sm font-medium">Max Files</label>
            <p className="text-xs text-muted-foreground">
              Maximum number of files to review per PR (default: 500)
            </p>
          </div>
          <div>
            <label className="text-sm font-medium">Confidence Floor</label>
            <p className="text-xs text-muted-foreground">
              Findings below this confidence are dropped (default: 75)
            </p>
          </div>
          <div>
            <label className="text-sm font-medium">Max Findings</label>
            <p className="text-xs text-muted-foreground">
              Maximum findings per review (default: 25)
            </p>
          </div>
          <div>
            <label className="text-sm font-medium">LLM Model</label>
            <p className="text-xs text-muted-foreground">
              Model used for review agents (configured via backend env)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
