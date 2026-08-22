import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Sidenav } from "@/components/layout/Sidenav";
import { Topbar } from "@/components/layout/Topbar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/signin");
  }

  return (
    <div className="min-h-screen bg-background">
      <Sidenav />
      <div className="ml-64">
        <Topbar />
        <main className="p-8">{children}</main>
      </div>
    </div>
  );
}
