import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { DashboardContent } from "@/components/dashboard/dashboard-content";

export default function DashboardPage() {
  return (
    <div className="flex h-screen bg-[#0B0F14] text-white overflow-hidden">
      <DashboardSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-light mb-2">Dashboard</h1>
            <p className="text-gray-400 font-light">
              Your analyses and forecasts at a glance
            </p>
          </div>

          <DashboardContent />
        </div>
      </main>
    </div>
  );
}
