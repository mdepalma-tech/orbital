import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { BuildForm } from "@/components/dashboard/build-form";
import { randomUUID } from "@/lib/utils";

export default async function BuildModelPage({
  searchParams,
}: {
  searchParams: Promise<{ projectId?: string }>;
}) {
  const { projectId: pid } = await searchParams;
  const projectId = pid || randomUUID();

  return (
    <div className="flex h-screen bg-[#0B0F14] text-white overflow-hidden">
      {/* Left Sidebar */}
      <DashboardSidebar />

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-light mb-2">Build a New Model</h1>
            <p className="text-gray-400 font-light">
              Upload your Shopify orders data to begin causal analysis
            </p>
          </div>

          <BuildForm projectId={projectId} />
        </div>
      </main>
    </div>
  );
}
