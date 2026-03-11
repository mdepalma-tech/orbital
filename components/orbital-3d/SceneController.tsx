"use client";

import { VARIABLES, type OrbitalGroup } from "./data";
import { RevenueCore } from "./RevenueCore";
import { OrbitalNode } from "./OrbitalNode";
import { OrbitPath } from "./OrbitPath";
import { OrbitControls } from "@react-three/drei";

const GROUPS: OrbitalGroup[] = ["funnel", "paidMedia", "demand", "events"];

interface SceneControllerProps {
  phase: "chaos" | "activating" | "orbital";
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

export function SceneController({
  phase,
  selectedId,
  hoveredId,
  onSelect,
  onHover,
}: SceneControllerProps) {
  const selectedGroup = selectedId
    ? VARIABLES.find((v) => v.id === selectedId)?.group ?? null
    : null;
  const hoveredGroup = hoveredId
    ? VARIABLES.find((v) => v.id === hoveredId)?.group ?? null
    : null;

  return (
    <>
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        enableDamping
        dampingFactor={0.05}
        rotateSpeed={0.4}
        minPolarAngle={0}
        maxPolarAngle={Math.PI}
      />

      <ambientLight intensity={0.08} />
      <hemisphereLight
        color="#6366f1"
        groundColor="#0B0F14"
        intensity={0.18}
      />
      <directionalLight
        position={[5, 8, 6]}
        intensity={0.55}
        color="#c4b5fd"
      />
      <directionalLight
        position={[-4, -3, -5]}
        intensity={0.12}
        color="#60a5fa"
      />
      <directionalLight
        position={[0, -6, 3]}
        intensity={0.08}
        color="#818cf8"
      />
      <fog attach="fog" args={["#0B0F14", 14, 35]} />

      <group>
        <RevenueCore phase={phase} />

        {GROUPS.map((g) => (
          <OrbitPath
            key={g}
            group={g}
            phase={phase}
            isHighlighted={g === selectedGroup || g === hoveredGroup}
          />
        ))}

        {VARIABLES.map((v) => (
          <OrbitalNode
            key={v.id}
            variable={v}
            phase={phase}
            selectedId={selectedId}
            hoveredId={hoveredId}
            onSelect={onSelect}
            onHover={onHover}
          />
        ))}
      </group>
    </>
  );
}
