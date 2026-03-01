import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { EventsUploadSection } from "@/components/dashboard/events-upload-section";
import { RunModelButton } from "@/components/dashboard/run-model-button";
import { randomUUID } from "@/lib/utils";

export default async function EventsPage({
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
            <h1 className="text-3xl font-light mb-2">Add Events</h1>
            <p className="text-gray-400 font-light">
              Define the key events that may have influenced your store&apos;s performance
            </p>
          </div>

          {/* Event type explainer */}
          <div className="grid md:grid-cols-2 gap-4 mb-8">
            <div className="p-5 rounded-xl border border-amber-500/20 bg-amber-500/5">
              <h4 className="text-amber-400 font-light mb-2">Step Events</h4>
              <p className="text-sm text-gray-400 font-light leading-relaxed">
                A <strong className="text-white">step event</strong> is a permanent change that shifts your baseline going forward.
                Examples: launching a new product line, changing your pricing structure, redesigning your site,
                or switching fulfillment providers. The effect persists after the event date.
              </p>
            </div>
            <div className="p-5 rounded-xl border border-cyan-500/20 bg-cyan-500/5">
              <h4 className="text-cyan-400 font-light mb-2">Pulse Events</h4>
              <p className="text-sm text-gray-400 font-light leading-relaxed">
                A <strong className="text-white">pulse event</strong> is a temporary spike that fades after it ends.
                Examples: a Black Friday sale, a flash promotion, a viral social media post,
                or a seasonal holiday campaign. The effect is bounded by start and end dates.
              </p>
            </div>
          </div>

          <EventsUploadSection projectId={projectId} />

          <div className="flex gap-4 pt-8">
            <a
              href={`/dashboard/build/ad-spend?projectId=${projectId}`}
              className="px-8 py-4 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300 text-center"
            >
              Back
            </a>
            <RunModelButton projectId={projectId} />
          </div>
        </div>
      </main>
    </div>
  );
}
