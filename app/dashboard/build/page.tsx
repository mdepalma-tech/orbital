import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { OrdersUploadSection } from "@/components/dashboard/orders-upload-section";
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

          {/* Model Builder Form */}
          <div className="space-y-6">
            {/* Step 1: Model Name */}
            <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
              <label className="block mb-4">
                <span className="text-sm text-gray-400 font-light">Analysis Name</span>
                <input
                  type="text"
                  placeholder="e.g., Q1 2024 Revenue Analysis"
                  className="mt-2 w-full px-4 py-3 bg-black/40 border border-white/10 rounded-lg text-white placeholder-gray-600 focus:border-blue-500/50 focus:outline-none font-light"
                />
              </label>
              <p className="text-xs text-gray-500 font-light">
                Give your analysis a descriptive name for easy reference
              </p>
            </div>

            {/* Step 2: Upload Orders CSV */}
            <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
              <div className="mb-4">
                <h3 className="text-lg font-light mb-2">Upload Shopify Orders</h3>
                <p className="text-sm text-gray-400 font-light">
                  Upload your Shopify orders export to analyze revenue patterns and order trends
                </p>
              </div>
              
              <OrdersUploadSection projectId={projectId} />
            </div>

            <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/30">
              <p className="text-sm text-blue-300 font-light">
                💡 <strong>Next steps:</strong> After uploading your orders data, we'll add channel spend data and run the causal analysis to identify what truly drives your revenue.
              </p>
            </div>

            {/* Actions */}
            <div className="flex gap-4 pt-4">
              <a
                href="/dashboard"
                className="px-8 py-4 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300 text-center"
              >
                Cancel
              </a>
              <a
                href={`/dashboard/build/ad-spend?projectId=${projectId}`}
                className="flex-1 px-8 py-4 bg-gradient-to-r from-blue-500 to-violet-500 backdrop-blur-md border border-white/20 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-blue-500/50 transition-all duration-300 text-center"
              >
                Next: Upload Ad Spend
              </a>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
