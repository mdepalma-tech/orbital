"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface RevenueCoreProps {
  phase: "chaos" | "activating" | "orbital";
}

export function RevenueCore({ phase }: RevenueCoreProps) {
  const coreRef = useRef<THREE.Mesh>(null!);
  const wireRef = useRef<THREE.Mesh>(null!);
  const innerGlowRef = useRef<THREE.Mesh>(null!);
  const outerGlowRef = useRef<THREE.Mesh>(null!);
  const ring1Ref = useRef<THREE.Mesh>(null!);
  const ring2Ref = useRef<THREE.Mesh>(null!);
  const lightRef = useRef<THREE.PointLight>(null!);
  const timeRef = useRef(0);
  void phase;

  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;

    // Slow, dignified breathing — ~0.25 Hz (was 4.2, very fast/tacky)
    const breathe = 0.5 + 0.5 * Math.sin(t * 1.6);

    // Core: slow dual-axis rotation
    if (coreRef.current) {
      coreRef.current.rotation.y += delta * 0.07;
      coreRef.current.rotation.x += delta * 0.025;
      const mat = coreRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = THREE.MathUtils.lerp(
        mat.emissiveIntensity,
        0.55 + breathe * 0.25,
        delta * 2.5
      );
    }

    // Wireframe shell: counter-rotates for depth and motion
    if (wireRef.current) {
      wireRef.current.rotation.y -= delta * 0.04;
      wireRef.current.rotation.z += delta * 0.015;
      const mat = wireRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = THREE.MathUtils.lerp(mat.opacity, 0.07 + breathe * 0.04, delta * 2);
    }

    // Inner glow: subtle breath, minimal scale range
    if (innerGlowRef.current) {
      const target = 1.65 + breathe * 0.12;
      innerGlowRef.current.scale.setScalar(
        THREE.MathUtils.lerp(innerGlowRef.current.scale.x, target, delta * 3)
      );
      const mat = innerGlowRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = THREE.MathUtils.lerp(mat.opacity, 0.10 + breathe * 0.04, delta * 3);
    }

    // Outer corona: very slow, barely perceptible
    if (outerGlowRef.current) {
      const target = 4.2 + breathe * 0.2;
      outerGlowRef.current.scale.setScalar(
        THREE.MathUtils.lerp(outerGlowRef.current.scale.x, target, delta * 1.2)
      );
      const mat = outerGlowRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = THREE.MathUtils.lerp(mat.opacity, 0.022 + breathe * 0.008, delta * 1.2);
    }

    // Ring 1: slow rotation on Z
    if (ring1Ref.current) {
      ring1Ref.current.rotation.z += delta * 0.05;
    }

    // Ring 2: different axis for depth
    if (ring2Ref.current) {
      ring2Ref.current.rotation.x += delta * 0.035;
    }

    // Point light breathes with the core
    if (lightRef.current) {
      lightRef.current.intensity = THREE.MathUtils.lerp(
        lightRef.current.intensity,
        1.0 + breathe * 0.35,
        delta * 2
      );
    }
  });

  return (
    <group>
      {/* Core: faceted icosahedron — crystalline, premium */}
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[0.48, 0]} />
        <meshStandardMaterial
          color="#5c6bff"
          emissive="#3b3fd8"
          emissiveIntensity={0.5}
          roughness={0.05}
          metalness={0.88}
        />
      </mesh>

      {/* Wireframe shell — counter-rotates, creates depth without heaviness */}
      <mesh ref={wireRef}>
        <icosahedronGeometry args={[0.51, 0]} />
        <meshBasicMaterial
          color="#a5b4fc"
          wireframe
          transparent
          opacity={0.08}
          depthWrite={false}
        />
      </mesh>

      {/* Inner glow — tight, minimal halo */}
      <mesh ref={innerGlowRef} scale={1.65}>
        <sphereGeometry args={[0.48, 20, 20]} />
        <meshBasicMaterial
          color="#6366f1"
          transparent
          opacity={0.10}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Outer corona — very large, barely visible atmospheric depth */}
      <mesh ref={outerGlowRef} scale={4.2}>
        <sphereGeometry args={[0.48, 14, 14]} />
        <meshBasicMaterial
          color="#4338ca"
          transparent
          opacity={0.022}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Orbital ring 1 — primary, tilted */}
      <mesh ref={ring1Ref} rotation={[Math.PI / 2.5, 0.25, 0]}>
        <torusGeometry args={[0.95, 0.007, 6, 80]} />
        <meshBasicMaterial
          color="#818cf8"
          transparent
          opacity={0.28}
          depthWrite={false}
        />
      </mesh>

      {/* Orbital ring 2 — secondary, different plane */}
      <mesh ref={ring2Ref} rotation={[0.3, Math.PI / 5, Math.PI / 4]}>
        <torusGeometry args={[0.72, 0.005, 6, 64]} />
        <meshBasicMaterial
          color="#a5b4fc"
          transparent
          opacity={0.18}
          depthWrite={false}
        />
      </mesh>

      <pointLight
        ref={lightRef}
        color="#818cf8"
        intensity={1.0}
        distance={22}
        decay={2}
      />
    </group>
  );
}
