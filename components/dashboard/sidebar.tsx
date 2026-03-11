"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoutButton } from "@/components/logout-button";
import { randomUUID } from "@/lib/utils";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: "📊" },
  { name: "Analyses", href: "/dashboard/analyses", icon: "🧠" },
  { name: "Data Sources", href: "/dashboard/sources", icon: "🔌" },
  { name: "Insights", href: "/dashboard/insights", icon: "💡" },
  { name: "Anomalies", href: "/dashboard/anomalies", icon: "🚨" },
  { name: "Settings", href: "/dashboard/settings", icon: "⚙️" },
];

export function DashboardSidebar() {
  const pathname = usePathname();
  const [hasAnalyses, setHasAnalyses] = useState(false);

  useEffect(() => {
    fetch("/api/analyses")
      .then((r) => r.json())
      .then((data) => setHasAnalyses((data?.analyses?.length ?? 0) > 0))
      .catch(() => {});
  }, []);

  return (
    <aside className="w-64 bg-black/40 border-r border-white/10 flex flex-col backdrop-blur-sm">
      {/* Logo */}
      <div className="p-6 border-b border-white/10">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-violet-500" />
          <span className="text-xl font-light tracking-wider">ORBITAL</span>
        </Link>
      </div>

      {/* Build new model - top when user has analyses */}
      {hasAnalyses && (
        <div className="p-4 border-b border-white/10">
          <Link
            href={`/dashboard/build?projectId=${randomUUID()}`}
            className="flex items-center gap-3 px-4 py-3 rounded-lg font-light bg-gradient-to-r from-blue-500/20 to-violet-500/20 border border-blue-500/30 text-white hover:from-blue-500/30 hover:to-violet-500/30 transition-all"
          >
            <span className="text-xl">➕</span>
            <span>Build New Model</span>
          </Link>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg font-light transition-all duration-200 ${
                isActive
                  ? "bg-gradient-to-r from-blue-500/20 to-violet-500/20 text-white border border-blue-500/30"
                  : "text-gray-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <span className="text-xl">{item.icon}</span>
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* User Section */}
      <div className="p-4 border-t border-white/10">
        <div className="mb-4 px-4 py-3 rounded-lg bg-white/5">
          <p className="text-xs text-gray-500 mb-1">Store Connected</p>
          <p className="text-sm font-light">my-store.myshopify.com</p>
        </div>
        <LogoutButton />
      </div>
    </aside>
  );
}
