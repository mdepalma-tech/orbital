import { createClient } from "@/lib/supabase/server";
import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { AnalysesList } from "@/components/dashboard/analyses-list";

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <div className="flex h-screen bg-[#0B0F14] text-white overflow-hidden">
      <DashboardSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-light mb-2">Your Analyses</h1>
            <p className="text-gray-400 font-light">
              Build and monitor causal intelligence models for your store
            </p>
          </div>

          <AnalysesList userId={user?.id ?? ""} />
        </div>
      </main>
    </div>
  );
}
