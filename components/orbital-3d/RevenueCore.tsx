"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface RevenueCoreProps {
  phase: "chaos" | "activating" | "orbital";
}

export function RevenueCore({ phase }: RevenueCoreProps) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const glowRef = useRef<THREE.Mesh>(null!);
  const lightRef = useRef<THREE.PointLight>(null!);

  const targetScale = 1.0;
  const targetEmissive = 0.8;
  const targetLightIntensity = 1.8;
  const targetGlowScale = 3.0;
  void phase;

  const timeRef = useRef(0);

  useFrame((_, delta) => {
    if (!meshRef.current || !glowRef.current || !lightRef.current) return;
    timeRef.current += delta;

    const mat = meshRef.current.material as THREE.MeshStandardMaterial;
    const s = meshRef.current.scale.x;
    const newScale = THREE.MathUtils.lerp(s, targetScale, delta * 2);
    meshRef.current.scale.setScalar(newScale);

    mat.emissiveIntensity = THREE.MathUtils.lerp(
      mat.emissiveIntensity,
      targetEmissive,
      delta * 2
    );

    lightRef.current.intensity = THREE.MathUtils.lerp(
      lightRef.current.intensity,
      targetLightIntensity,
      delta * 2
    );

    // Pulse the glow sphere: a smooth sine wave with ~1.5s period
    const pulse = 0.5 + 0.5 * Math.sin(timeRef.current * 4.2);
    const baseGlowScale = targetGlowScale;
    const pulseGlowScale = baseGlowScale + pulse * 0.6;

    const gs = glowRef.current.scale.x;
    const newGlow = THREE.MathUtils.lerp(gs, pulseGlowScale, delta * 3);
    glowRef.current.scale.setScalar(newGlow);

    const glowMat = glowRef.current.material as THREE.MeshBasicMaterial;
    const baseOpacity = 0.14;
    const pulseOpacity = baseOpacity + pulse * 0.08;
    glowMat.opacity = THREE.MathUtils.lerp(
      glowMat.opacity,
      pulseOpacity,
      delta * 3
    );

    meshRef.current.rotation.y += delta * 0.15;
  });

  return (
    <group>
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.6, 32, 32]} />
        <meshStandardMaterial
          color="#6366f1"
          emissive="#4f46e5"
          emissiveIntensity={0.3}
          roughness={0.2}
          metalness={0.7}
        />
      </mesh>

      {/* Glow sphere instead of flat plane — no visible square edges */}
      <mesh ref={glowRef} scale={1.8}>
        <sphereGeometry args={[0.6, 32, 32]} />
        <meshBasicMaterial
          color="#6366f1"
          transparent
          opacity={0.06}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      <pointLight
        ref={lightRef}
        color="#818cf8"
        intensity={0.6}
        distance={20}
        decay={2}
      />
    </group>
  );
}
