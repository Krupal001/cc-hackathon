"use client";

import { signIn } from "next-auth/react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Github, Shield, Loader2 } from "lucide-react";

export default function SignInPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (status === "authenticated") {
      router.push("/dashboard");
    }
  }, [status, router]);

  const handleSignIn = () => {
    setLoading(true);
    signIn("github", { callbackUrl: "/dashboard" });
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
            <Shield className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">CodeSentinel</h1>
          <p className="text-center text-sm text-muted-foreground">
            AI-powered GitHub PR review with multi-agent analysis.
            <br />
            Sign in with GitHub to get started.
          </p>
        </div>

        <button
          onClick={handleSignIn}
          disabled={loading || status === "loading"}
          className="flex w-full items-center justify-center gap-3 rounded-md bg-primary px-4 py-3 font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading || status === "loading" ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Github className="h-5 w-5" />
          )}
          {loading || status === "loading" ? "Redirecting..." : "Sign in with GitHub"}
        </button>

        <p className="text-center text-xs text-muted-foreground">
          By signing in, you agree to connect your GitHub account for PR review analysis.
        </p>
      </div>
    </div>
  );
}
