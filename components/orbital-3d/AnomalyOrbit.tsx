"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { Html } from "@react-three/drei";

const RADIUS_A = 3.2;
const RADIUS_B = 2.0;
const TILT_X_DEG = 22;
const TILT_Z_DEG = 6;
const CYCLE_SECONDS = 8;
const DEV_START = 0.52;
const DEV_END = 0.76;
const DEV_AMPLITUDE = 1.2;
const TRAIL_SEGMENTS = 250;
const TRAIL_FADE_SECONDS = 2.5;

const EULER = new THREE.Euler(
  (TILT_X_DEG * Math.PI) / 180,
  0,
  (TILT_Z_DEG * Math.PI) / 180,
  "XYZ"
);

const _v = new THREE.Vector3();
const _colorRed = new THREE.Color(0xef4444);
const _colorBlue = new THREE.Color(0x818cf8);

function expectedPos(fraction: number, out: THREE.Vector3): void {
  const θ = fraction * Math.PI * 2;
  out.set(RADIUS_A * Math.cos(θ), 0, RADIUS_B * Math.sin(θ));
  out.applyEuler(EULER);
}

function deviationAmount(fraction: number): number {
  if (fraction < DEV_START || fraction > DEV_END) return 0;
  const t = (fraction - DEV_START) / (DEV_END - DEV_START);
  return Math.sin(t * Math.PI) * DEV_AMPLITUDE;
}

function actualPos(fraction: number, out: THREE.Vector3): void {
  expectedPos(fraction, out);
  const dev = deviationAmount(fraction);
  if (dev > 0.001) {
    _v.copy(out).normalize();
    out.addScaledVector(_v, dev);
  }
}

export function AnomalyOrbit() {
  const sphereRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const ghostRef = useRef<THREE.Mesh>(null);
  const trailMatRef = useRef<THREE.LineBasicMaterial>(null);
  const labelRef = useRef<HTMLDivElement>(null);
  const labelGroupRef = useRef<THREE.Group>(null);

  const trailIdx = useRef(0);
  const wasDeviating = useRef(false);
  const fadeStart = useRef<number | null>(null);
  const posOut = useRef(new THREE.Vector3());
  const ghostOut = useRef(new THREE.Vector3());

  const expectedGeo = useMemo(() => {
    const segs = 128;
    const positions = new Float32Array((segs + 1) * 3);
    const v = new THREE.Vector3();
    for (let i = 0; i <= segs; i++) {
      expectedPos(i / segs, v);
      positions[i * 3] = v.x;
      positions[i * 3 + 1] = v.y;
      positions[i * 3 + 2] = v.z;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geo;
  }, []);

  const trailGeo = useMemo(() => {
    const positions = new Float32Array(TRAIL_SEGMENTS * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setDrawRange(0, 0);
    return geo;
  }, []);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const frac = (t / CYCLE_SECONDS) % 1;
    const dev = deviationAmount(frac);
    const isDeviating = dev > 0.01;
    const targetColor = isDeviating ? _colorRed : _colorBlue;

    actualPos(frac, posOut.current);

    if (sphereRef.current) {
      sphereRef.current.position.copy(posOut.current);
      const mat = sphereRef.current.material as THREE.MeshStandardMaterial;
      mat.color.lerp(targetColor, 0.07);
      mat.emissive.lerp(targetColor, 0.07);
    }

    if (glowRef.current) {
      glowRef.current.position.copy(posOut.current);
      const mat = glowRef.current.material as THREE.MeshBasicMaterial;
      mat.color.lerp(targetColor, 0.07);
      mat.opacity = THREE.MathUtils.lerp(
        mat.opacity,
        isDeviating ? 0.3 : 0.12,
        0.05
      );
    }

    expectedPos(frac, ghostOut.current);
    if (ghostRef.current) {
      ghostRef.current.position.copy(ghostOut.current);
      const mat = ghostRef.current.material as THREE.MeshStandardMaterial;
      mat.opacity = THREE.MathUtils.lerp(
        mat.opacity,
        isDeviating ? 0.4 : 0,
        0.06
      );
    }

    if (labelGroupRef.current) {
      labelGroupRef.current.position.copy(posOut.current);
    }
    if (labelRef.current) {
      const targetOpacity = isDeviating ? 1 : 0;
      const cur = parseFloat(labelRef.current.style.opacity || "0");
      labelRef.current.style.opacity = String(
        cur + (targetOpacity - cur) * 0.06
      );
    }

    if (isDeviating) {
      if (!wasDeviating.current) {
        trailIdx.current = 0;
        fadeStart.current = null;
        wasDeviating.current = true;
      }
      if (trailIdx.current < TRAIL_SEGMENTS) {
        const attr = trailGeo.getAttribute(
          "position"
        ) as THREE.BufferAttribute;
        attr.setXYZ(
          trailIdx.current,
          posOut.current.x,
          posOut.current.y,
          posOut.current.z
        );
        attr.needsUpdate = true;
        trailIdx.current++;
        trailGeo.setDrawRange(0, trailIdx.current);
      }
      if (trailMatRef.current) trailMatRef.current.opacity = 0.85;
    } else {
      if (wasDeviating.current) {
        fadeStart.current = t;
        wasDeviating.current = false;
      }
      if (trailMatRef.current && fadeStart.current !== null) {
        const elapsed = t - fadeStart.current;
        trailMatRef.current.opacity = Math.max(
          0,
          0.85 * (1 - elapsed / TRAIL_FADE_SECONDS)
        );
        if (elapsed > TRAIL_FADE_SECONDS) {
          trailGeo.setDrawRange(0, 0);
          trailIdx.current = 0;
          fadeStart.current = null;
        }
      }
    }
  });

  return (
    <group>
      <threeLine geometry={expectedGeo}>
        <lineBasicMaterial
          color="#6366f1"
          transparent
          opacity={0.2}
          depthWrite={false}
        />
      </threeLine>

      <threeLine geometry={trailGeo}>
        <lineBasicMaterial
          ref={trailMatRef}
          color="#ef4444"
          transparent
          opacity={0}
          depthWrite={false}
        />
      </threeLine>

      <mesh ref={ghostRef}>
        <sphereGeometry args={[0.09, 16, 16]} />
        <meshStandardMaterial
          color="#818cf8"
          emissive="#818cf8"
          emissiveIntensity={0.3}
          transparent
          opacity={0}
        />
      </mesh>

      <mesh ref={sphereRef}>
        <sphereGeometry args={[0.13, 24, 24]} />
        <meshStandardMaterial
          color="#818cf8"
          emissive="#818cf8"
          emissiveIntensity={0.6}
          roughness={0.3}
          metalness={0.5}
        />
      </mesh>

      <mesh ref={glowRef}>
        <sphereGeometry args={[0.3, 16, 16]} />
        <meshBasicMaterial color="#818cf8" transparent opacity={0.12} />
      </mesh>

      <group ref={labelGroupRef}>
        <Html distanceFactor={10} style={{ pointerEvents: "none" }}>
          <div
            ref={labelRef}
            style={{ opacity: 0, transform: "translateY(-32px)" }}
            className="whitespace-nowrap text-[10px] font-light tracking-wider text-red-400 px-2 py-1 rounded bg-red-500/10 border border-red-500/20 backdrop-blur-sm"
          >
            anomaly detected
          </div>
        </Html>
      </group>
    </group>
  );
}
