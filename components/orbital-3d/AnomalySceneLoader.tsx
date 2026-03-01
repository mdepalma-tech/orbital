"use client";

import dynamic from "next/dynamic";

const AnomalyScene = dynamic(
  () =>
    import("@/components/orbital-3d/AnomalyScene").then(
      (m) => m.AnomalyScene
    ),
  { ssr: false }
);

export function AnomalySceneLoader() {
  return <AnomalyScene />;
}
