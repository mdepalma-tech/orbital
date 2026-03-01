import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { MetaAdsUploadSection } from "@/components/dashboard/meta-ads-upload-section";
import { GoogleAdsUploadSection } from "@/components/dashboard/google-ads-upload-section";
import { TikTokAdsUploadSection } from "@/components/dashboard/tiktok-ads-upload-section";
import { randomUUID } from "@/lib/utils";

export default async function AdSpendPage({
  searchParams,
}: {
  searchParams: Promise<{ projectId?: string }>;
}) {
  const { projectId: pid } = await searchParams;
  const projectId = pid || randomUUID();

  return (
    <div className="flex h-screen bg-[#0B0F14] text-white overflow-hidden">
      <DashboardSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-light mb-2">Upload Ad Spend</h1>
            <p className="text-gray-400 font-light">
              Add your marketing channel spend data to measure incremental impact
            </p>
          </div>

          <div className="space-y-6">
            <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
              <div className="mb-4">
                <h3 className="text-lg font-light mb-2">Meta Ads Campaign Export</h3>
                <p className="text-sm text-gray-400 font-light">
                  Upload a Meta Ads campaign-level CSV segmented by day. Aggregates to meta_spend.
                </p>
              </div>

              <MetaAdsUploadSection projectId={projectId} />
            </div>

            <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
              <div className="mb-4">
                <h3 className="text-lg font-light mb-2">Google Ads Campaign Export</h3>
                <p className="text-sm text-gray-400 font-light">
                  Upload a Google Ads campaign-level CSV segmented by day. Aggregates to google_spend.
                </p>
              </div>

              <GoogleAdsUploadSection projectId={projectId} />
            </div>

            <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
              <div className="mb-4">
                <h3 className="text-lg font-light mb-2">TikTok Ads Campaign Export</h3>
                <p className="text-sm text-gray-400 font-light">
                  Upload a TikTok Ads campaign-level CSV segmented by day. Aggregates to tiktok_spend.
                </p>
              </div>

              <TikTokAdsUploadSection projectId={projectId} />
            </div>

            <div className="p-4 rounded-lg bg-violet-500/10 border border-violet-500/30">
              <p className="text-sm text-violet-300 font-light">
                <strong>Meta Ads:</strong> date/day + amount_spent → meta_spend.{" "}
                <strong>Google Ads:</strong> day/date + cost + campaign → google_spend.{" "}
                <strong>TikTok Ads:</strong> date/day + spend → tiktok_spend.
              </p>
            </div>

            <div className="flex gap-4 pt-4">
              <a
                href={`/dashboard/build?projectId=${projectId}`}
                className="px-8 py-4 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300 text-center"
              >
                Back
              </a>
              <a
                href={`/dashboard/build/events?projectId=${projectId}`}
                className="flex-1 px-8 py-4 bg-gradient-to-r from-violet-500 to-blue-500 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-violet-500/50 transition-all duration-300 text-center"
              >
                Next: Add Events
              </a>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
