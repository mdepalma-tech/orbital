"use client";

import dynamic from "next/dynamic";

const HeroSection = dynamic(
  () =>
    import("@/components/orbital-3d/HeroSection").then((m) => m.HeroSection),
  { ssr: false }
);

export function HeroSectionLoader() {
  return <HeroSection />;
}
