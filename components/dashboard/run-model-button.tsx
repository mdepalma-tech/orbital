"use client";

import { useRouter } from "next/navigation";

export function RunModelButton({ projectId }: { projectId: string }) {
  const router = useRouter();

  return (
    <div className="flex-1">
      <button
        onClick={() => router.push(`/dashboard/build/run?projectId=${projectId}`)}
        className="w-full px-8 py-4 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-cyan-500/50 transition-all duration-300 text-center"
      >
        Finish Setup &amp; Run Model
      </button>
    </div>
  );
}
