"use client";

import { signIn } from "next-auth/react";
import { Github, Shield } from "lucide-react";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center gap-4">
          <Shield className="h-12 w-12 text-primary" />
          <h1 className="text-2xl font-bold">CodeSentinel</h1>
          <p className="text-sm text-muted-foreground">
            AI-powered GitHub PR review with multi-agent analysis
          </p>
        </div>

        <button
          onClick={() => signIn("github", { callbackUrl: "/dashboard" })}
          className="flex w-full items-center justify-center gap-3 rounded-md bg-primary px-4 py-3 font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          <Github className="h-5 w-5" />
          Sign in with GitHub
        </button>

        <p className="text-center text-xs text-muted-foreground">
          &copy; 2024 CodeSentinel
        </p>
      </div>
    </div>
  );
}
