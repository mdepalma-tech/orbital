"use client";

import "@/components/orbital-3d/r3f-extend";
import { useState, useCallback, useEffect } from "react";
import { Canvas } from "@react-three/fiber";
import { PerspectiveCamera } from "@react-three/drei";
import { SceneController } from "./SceneController";
import { SidePanel } from "./SidePanel";

type Phase = "chaos" | "activating" | "orbital";

export function HeroSection() {
  const [phase, setPhase] = useState<Phase>("chaos");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const activate = useCallback(() => {
    if (phase !== "chaos") return;
    setPhase("activating");
    setTimeout(() => setPhase("orbital"), 2800);
  }, [phase]);

  const handleSelect = useCallback(
    (id: string) => {
      setSelectedId((prev) => (prev === id ? null : id));
    },
    []
  );

  const handleClose = useCallback(() => setSelectedId(null), []);

  const handlePointerMissed = useCallback(() => {
    if (phase === "chaos") {
      activate();
      return;
    }
    setSelectedId(null);
  }, [phase, activate]);

  useEffect(() => {
    return () => {
      document.body.style.cursor = "default";
    };
  }, []);

  return (
    <section className="relative z-10 flex flex-col items-center px-6 -mt-2">
      {/* Top: Headline */}
      <div className="text-center">
        {phase === "chaos" && (
          <p className="text-xs uppercase tracking-[0.25em] text-gray-500 mb-3 font-light">
            Your growth data is fragmented.
          </p>
        )}
        {phase === "orbital" && (
          <p className="text-xs uppercase tracking-[0.25em] text-emerald-400/70 mb-3 font-light">
            Structure revealed.
          </p>
        )}

        <h1 className="text-4xl md:text-5xl lg:text-6xl font-light tracking-tight mb-2 leading-[1.1]">
          See What Actually Moves
          <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-violet-400 to-blue-400">
            Your E-Commerce Revenue.
          </span>
        </h1>

        {phase === "chaos" && (
          <p className="text-xs text-white font-light tracking-wide animate-pulse">
            Click to turn on Orbital
          </p>
        )}
        {phase === "orbital" && (
          <p className="text-xs text-white font-light tracking-wide">
            Click any variable to explore
          </p>
        )}
      </div>

      {/* Middle: 3D Animation */}
      <div className="w-screen h-[65vh] lg:h-[82vh] relative -my-8 lg:-my-14 flex-shrink-0">
        <Canvas
          dpr={[1, 2]}
          onPointerMissed={handlePointerMissed}
          style={{
            background: "transparent",
            cursor: phase === "chaos" ? "pointer" : "grab",
          }}
        >
          <PerspectiveCamera makeDefault position={[0, 1, 13]} fov={50} />
          <SceneController
            phase={phase}
            selectedId={selectedId}
            hoveredId={hoveredId}
            onSelect={handleSelect}
            onHover={setHoveredId}
          />
        </Canvas>

        <SidePanel selectedId={selectedId} onClose={handleClose} />
      </div>

      {/* Bottom: Description + CTAs */}
      <div className="text-center max-w-3xl relative z-10">
        <p className="text-lg md:text-xl text-gray-400 mb-4 font-light leading-relaxed">
          Orbital models the forces driving your growth — quantifying
          incremental impact across revenue, traffic, and conversion using
          structured statistical modeling.
        </p>

        <p className="text-base text-gray-500 mb-8 font-light tracking-wide">
          Clear answers. No platform bias. No black box.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a
            href="#waitlist"
            className="px-8 py-4 bg-gradient-to-r from-blue-500/80 to-violet-500/80 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-blue-500/40 transition-all duration-300 text-base"
          >
            Join Waitlist
          </a>
          <a
            href="#waitlist"
            className="px-8 py-4 border border-white/15 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300 text-base text-gray-300"
          >
            Learn More
          </a>
        </div>
      </div>
    </section>
  );
}
