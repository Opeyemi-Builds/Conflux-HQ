import { Suspense } from "react";
import DashboardProvider from "@/components/dashboard/Provider";
import Shell from "@/components/dashboard/Shell";

export const metadata = { title: "Dashboard · Conflux HQ" };

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <DashboardProvider>
      <Suspense fallback={<div className="min-h-screen bg-cream flex items-center justify-center p-8 text-navy/50">Loading dashboard...</div>}>
        <Shell>{children}</Shell>
      </Suspense>
    </DashboardProvider>
  );
}
