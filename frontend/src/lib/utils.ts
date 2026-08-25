import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date | null): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  const tz = process.env.NEXT_PUBLIC_TIMEZONE || "Asia/Kolkata";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: tz,
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(d);
}

export function severityColor(severity: string): string {
  switch (severity) {
    case "critical":
      return "text-red-500 bg-red-500/10";
    case "warning":
      return "text-yellow-500 bg-yellow-500/10";
    case "info":
      return "text-blue-500 bg-blue-500/10";
    default:
      return "text-gray-500 bg-gray-500/10";
  }
}

export function scoreColor(score: number): string {
  if (score <= 1) return "text-red-500";
  if (score <= 2) return "text-orange-500";
  if (score <= 3) return "text-yellow-500";
  if (score <= 4) return "text-green-500";
  return "text-emerald-500";
}
