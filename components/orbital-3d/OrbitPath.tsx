"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { OrbitalGroup, GROUP_CONFIG } from "./data";

interface OrbitPathProps {
  group: OrbitalGroup;
  phase: "chaos" | "activating" | "orbital";
  isHighlighted: boolean;
}

const GROUP_NODE_COUNT: Record<OrbitalGroup, number> = {
  funnel: 3,
  paidMedia: 3,
  demand: 3,
  events: 4,
};

export function OrbitPath({ group, phase, isHighlighted }: OrbitPathProps) {
  const config = GROUP_CONFIG[group];
  const materialRef = useRef<THREE.LineBasicMaterial>(null!);
  const trailTimeRef = useRef(0);
  const segments = 128;

  const nodeCount = GROUP_NODE_COUNT[group];
  const fullOrbitTime = (2 * Math.PI) / config.speed;
  const trailDuration = Math.min(1.8, fullOrbitTime / nodeCount);

  const geometry = useMemo(() => {
    const a = config.radius;
    const b = config.radius * config.eccentricity;
    const euler = new THREE.Euler(
      (config.tiltXDeg * Math.PI) / 180,
      0,
      (config.tiltZDeg * Math.PI) / 180,
      "XYZ"
    );
    const positions = new Float32Array((segments + 1) * 3);
    const v = new THREE.Vector3();

    for (let i = 0; i <= segments; i++) {
      const angle = (i / segments) * Math.PI * 2;
      v.set(a * Math.cos(angle), 0, b * Math.sin(angle));
      v.applyEuler(euler);
      positions[i * 3] = v.x;
      positions[i * 3 + 1] = v.y;
      positions[i * 3 + 2] = v.z;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setDrawRange(0, 0);
    return geo;
  }, [config, segments]);

  useFrame((_, delta) => {
    if (!materialRef.current) return;

    if (phase === "chaos") {
      trailTimeRef.current = 0;
      geometry.setDrawRange(0, 0);
      materialRef.current.opacity = 0;
      return;
    }

    trailTimeRef.current += delta;

    const progress = Math.min(1, trailTimeRef.current / trailDuration);
    const drawCount = Math.max(2, Math.floor(progress * (segments + 1)));
    geometry.setDrawRange(0, drawCount);

    const targetOpacity = isHighlighted ? 0.55 : 0.25;
    materialRef.current.opacity = THREE.MathUtils.lerp(
      materialRef.current.opacity,
      targetOpacity * progress,
      delta * 4
    );
  });

  return (
    <line geometry={geometry}>
      <lineBasicMaterial
        ref={materialRef}
        color={isHighlighted ? "#818cf8" : "#a5b4fc"}
        transparent
        opacity={0}
        depthWrite={false}
      />
    </line>
  );
}
