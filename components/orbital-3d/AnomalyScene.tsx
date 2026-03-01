"use client";

import { useRef, useState, useEffect } from "react";
import { Canvas } from "@react-three/fiber";
import { PerspectiveCamera } from "@react-three/drei";
import { AnomalyOrbit } from "./AnomalyOrbit";

export function AnomalyScene() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.05 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="w-full h-full">
      <Canvas
        dpr={[1, 1.5]}
        frameloop={visible ? "always" : "never"}
        style={{ background: "transparent" }}
      >
        <PerspectiveCamera makeDefault position={[0, 0.6, 7.5]} fov={45} />
        <ambientLight intensity={0.12} />
        <hemisphereLight
          color="#818cf8"
          groundColor="#0B0F14"
          intensity={0.15}
        />
        <directionalLight
          position={[4, 6, 5]}
          intensity={0.35}
          color="#c4b5fd"
        />
        <fog attach="fog" args={["#0B0F14", 12, 28]} />
        <group position={[0, 0.4, 0]}>
          <AnomalyOrbit />
        </group>
      </Canvas>
    </div>
  );
}
