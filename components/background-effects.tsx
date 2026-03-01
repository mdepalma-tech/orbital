"use client";

import { useEffect, useState } from "react";

interface Particle {
  left: string;
  width: string;
  height: string;
  duration: string;
  delay: string;
  opacity: number;
}

interface DataPoint {
  text: string;
  left: string;
  duration: string;
  delay: string;
}

export function BackgroundEffects() {
  const [particles, setParticles] = useState<Particle[]>([]);
  const [dataPoints, setDataPoints] = useState<DataPoint[]>([]);

  useEffect(() => {
    // Generate particles on client side
    const newParticles = Array.from({ length: 20 }, () => ({
      left: `${Math.random() * 100}%`,
      width: `${Math.random() * 3 + 1}px`,
      height: `${Math.random() * 3 + 1}px`,
      duration: `${Math.random() * 15 + 10}s`,
      delay: `${Math.random() * 5}s`,
      opacity: Math.random() * 0.5 + 0.3
    }));
    setParticles(newParticles);

    // Generate data points on client side
    const texts = ['0x4A2F...', '+2.3%', '//src', '→ 1.2k', '{ }', '$38k', 'fn(x)', '∆ +12', '[ ]', '0.95', 'ROI↑', 'σ=0.3'];
    const newDataPoints = texts.map(text => ({
      text,
      left: `${Math.random() * 90}%`,
      duration: `${Math.random() * 20 + 15}s`,
      delay: `${Math.random() * 8}s`
    }));
    setDataPoints(newDataPoints);
  }, []);

  return (
    <div className="fixed inset-0 z-0">
      <div className="absolute inset-0 bg-gradient-to-b from-[#0B0F14] via-[#0d1219] to-[#0B0F14]" />
      <div className="depth-layer-2" />
      <div className="depth-layer-1" />
      <div className="stars-bg" />
      <div className="grid-bg" />
      <div className="vignette" />
      
      {/* Floating Particles */}
      <div className="floating-particles">
        {/* Stars/Particles */}
        {particles.map((particle, i) => (
          <div
            key={`particle-${i}`}
            className="particle"
            style={{
              left: particle.left,
              width: particle.width,
              height: particle.height,
              animationDuration: particle.duration,
              animationDelay: particle.delay,
              opacity: particle.opacity
            }}
          />
        ))}
        
        {/* Floating Data Points */}
        {dataPoints.map((point, i) => (
          <div
            key={`data-${i}`}
            className="particle-data"
            style={{
              left: point.left,
              animationDuration: point.duration,
              animationDelay: point.delay,
            }}
          >
            {point.text}
          </div>
        ))}
      </div>
    </div>
  );
}

