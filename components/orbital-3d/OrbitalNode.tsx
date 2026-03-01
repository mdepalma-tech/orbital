"use client";

import { useRef, useMemo, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { OrbitalVariable, GROUP_CONFIG } from "./data";

interface OrbitalNodeProps {
  variable: OrbitalVariable;
  phase: "chaos" | "activating" | "orbital";
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

const _euler = new THREE.Euler();
const _orbitalOut = new THREE.Vector3();

function getOrbitalPosition(
  variable: OrbitalVariable,
  time: number,
  out: THREE.Vector3
): THREE.Vector3 {
  const config = GROUP_CONFIG[variable.group];
  const count =
    variable.group === "events"
      ? 4
      : variable.group === "demand"
      ? 3
      : 3;
  const angularOffset = (variable.orbitIndex / count) * Math.PI * 2;
  const angle = time * config.speed + angularOffset;

  const a = config.radius;
  const b = config.radius * config.eccentricity;

  _euler.set(
    (config.tiltXDeg * Math.PI) / 180,
    0,
    (config.tiltZDeg * Math.PI) / 180,
    "XYZ"
  );
  return out.set(a * Math.cos(angle), 0, b * Math.sin(angle)).applyEuler(_euler);
}

export function OrbitalNode({
  variable,
  phase,
  selectedId,
  hoveredId,
  onSelect,
  onHover,
}: OrbitalNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const [hovered, setHovered] = useState(false);
  const orbitalTimeRef = useRef(0);

  const chaosTarget = useRef(
    new THREE.Vector3(
      (Math.random() - 0.5) * 10,
      (Math.random() - 0.5) * 6,
      (Math.random() - 0.5) * 8
    )
  );
  const chaosPos = useRef(
    new THREE.Vector3(
      (Math.random() - 0.5) * 10,
      (Math.random() - 0.5) * 6,
      (Math.random() - 0.5) * 8
    )
  );
  const chaosSpeed = useRef(0.3 + Math.random() * 0.3);

  const isSelected = selectedId === variable.id;
  const isOtherSelected = selectedId !== null && !isSelected;
  const isOtherHovered =
    hoveredId !== null && hoveredId !== variable.id;

  const nodeColor = useMemo(() => new THREE.Color(variable.color), [variable.color]);

  useFrame((_, delta) => {
    if (!meshRef.current) return;
    const mat = meshRef.current.material as THREE.MeshStandardMaterial;

    if (phase !== "chaos") {
      orbitalTimeRef.current += delta;
    }

    if (phase === "chaos") {
      const pos = chaosPos.current;
      const target = chaosTarget.current;
      pos.lerp(target, delta * chaosSpeed.current);

      if (pos.distanceTo(target) < 0.3) {
        chaosTarget.current.set(
          (Math.random() - 0.5) * 10,
          (Math.random() - 0.5) * 6,
          (Math.random() - 0.5) * 8
        );
      }

      meshRef.current.position.copy(pos);
    } else {
      if (phase === "activating") {
        const orbitalPos = getOrbitalPosition(variable, orbitalTimeRef.current, _orbitalOut);
        meshRef.current.position.lerp(orbitalPos, delta * 1.8);
        chaosPos.current.copy(meshRef.current.position);
      } else {
        const orbitalPos = getOrbitalPosition(variable, orbitalTimeRef.current, _orbitalOut);
        meshRef.current.position.copy(orbitalPos);
      }
    }

    const targetScale = hovered || isSelected ? 1.4 : 1.0;
    const s = meshRef.current.scale.x;
    meshRef.current.scale.setScalar(
      THREE.MathUtils.lerp(s, targetScale, delta * 6)
    );

    const targetEmissive =
      isOtherSelected || isOtherHovered ? 0.1 : hovered || isSelected ? 0.9 : 0.5;
    mat.emissiveIntensity = THREE.MathUtils.lerp(
      mat.emissiveIntensity,
      targetEmissive,
      delta * 4
    );

    const targetOpacity = isOtherSelected || isOtherHovered ? 0.4 : 1.0;
    mat.opacity = THREE.MathUtils.lerp(mat.opacity, targetOpacity, delta * 4);
  });

  return (
    <mesh
      ref={meshRef}
      onClick={(e) => {
        e.stopPropagation();
        if (phase === "orbital") onSelect(variable.id);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
        onHover(variable.id);
        document.body.style.cursor = phase === "orbital" ? "pointer" : "default";
      }}
      onPointerOut={() => {
        setHovered(false);
        onHover(null);
        document.body.style.cursor = "default";
      }}
    >
      <sphereGeometry args={[0.2, 32, 32]} />
      <meshStandardMaterial
        color={nodeColor}
        emissive={nodeColor}
        emissiveIntensity={0.35}
        roughness={0.25}
        metalness={0.7}
        transparent
        opacity={1}
        envMapIntensity={1.2}
      />
      <Html
        distanceFactor={12}
        style={{ pointerEvents: "none", userSelect: "none" }}
      >
        <div style={{ transform: "translateY(-24px)" }} className="flex flex-col items-center">
          <div className="text-[11px] font-light tracking-wider text-white/60 px-1.5 py-0.5 rounded bg-black/40 backdrop-blur-sm whitespace-nowrap">
            {variable.label}
          </div>
        </div>
      </Html>
    </mesh>
  );
}
