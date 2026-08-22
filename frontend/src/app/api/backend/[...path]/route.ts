import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

async function proxy(req: NextRequest, params: { path: string[] }) {
  const path = params.path.join("/");
  const { search } = new URL(req.url);
  const target = `${BACKEND_URL}/${path}${search}`;

  const headers: HeadersInit = { "Content-Type": "application/json" };

  // Attach GitHub user ID from session for user-level data isolation
  const session = await getServerSession(authOptions);
  const githubUserId = (session as any)?.githubUserId;
  if (githubUserId) {
    headers["X-GitHub-User-Id"] = String(githubUserId);
  }

  let body: string | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.text();
  }

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body,
    cache: "no-store",
  });

  const data = await upstream.text();
  return new NextResponse(data, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
