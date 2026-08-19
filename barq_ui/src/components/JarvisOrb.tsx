'use client';
import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial, Stars, Points, PointMaterial } from '@react-three/drei';
import * as THREE from 'three';

export type OrbState = 'sleeping' | 'listening' | 'thinking' | 'speaking' | 'working';

interface OrbProps {
  aiState: OrbState;
}

const STATE_COLORS: Record<OrbState, string> = {
  sleeping: '#334155',
  listening: '#22d3ee',
  thinking: '#fbbf24',
  speaking: '#3b82f6',
  working: '#a855f7',
};

export default function JarvisOrb({ aiState }: OrbProps) {
  const coreRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const outerRef = useRef<THREE.Mesh>(null);
  const pointsRef = useRef<THREE.Points>(null);
  const starGroupRef = useRef<THREE.Group>(null);
  const trailRef = useRef<THREE.Group>(null);

  const color = STATE_COLORS[aiState] || STATE_COLORS.sleeping;

  const ringPositions = useMemo(() => {
    const pts: number[] = [];
    for (let i = 0; i < 220; i++) {
      const a = (i / 220) * Math.PI * 2;
      pts.push(Math.cos(a) * 2.35, Math.sin(a) * 0.32, Math.sin(a) * 2.35);
    }
    return new Float32Array(pts);
  }, []);

  const trailPositions = useMemo(() => {
    const pts: number[] = [];
    const count = 420;
    for (let i = 0; i < count; i++) {
      const radius = 5.5 + (i / count) * 9;
      const tilt = Math.cos(i * 12.9898) ;
      const a = i * 2.4;
      pts.push(
        Math.cos(a) * radius,
        Math.sin(a * 0.9) * radius * 0.35,
        Math.sin(a) * radius
      );
    }
    return new Float32Array(pts);
  }, []);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();

    if (coreRef.current) {
      coreRef.current.rotation.y += 0.006;
      coreRef.current.rotation.x += 0.002;
      let scale = 1;
      if (aiState === 'listening') scale = 1 + Math.sin(t * 5) * 0.05;
      else if (aiState === 'thinking') scale = 1 + Math.sin(t * 9) * 0.16;
      else if (aiState === 'speaking') scale = 1 + Math.sin(t * 13) * 0.11;
      else if (aiState === 'working') scale = 1 + Math.sin(t * 8) * 0.08;
      coreRef.current.scale.set(scale, scale, scale);
    }

    if (ringRef.current) {
      ringRef.current.rotation.z += 0.0028;
      const pulse = aiState === 'speaking' || aiState === 'working'
        ? 1 + Math.sin(t * 10) * 0.04 : 1;
      ringRef.current.scale.setScalar(pulse);
    }

    if (outerRef.current) {
      outerRef.current.rotation.y -= 0.0035;
      outerRef.current.scale.setScalar(1 + Math.sin(t * 2.2) * 0.03);
      const mat = outerRef.current.material as THREE.MeshBasicMaterial;
      if (mat) {
        mat.color.setHex(aiState === 'sleeping' ? 0x475569 : 0x22d3ee);
        mat.opacity = aiState === 'sleeping' ? 0.1 : 0.28 + Math.sin(t * 6) * 0.08;
      }
    }

    if (pointsRef.current) pointsRef.current.rotation.y += 0.006;

    // animated starfield
    if (starGroupRef.current) starGroupRef.current.rotation.y = t * 0.02;
    if (trailRef.current) trailRef.current.rotation.y = -t * 0.03;
  });

  return (
    <>
      <ambientLight intensity={0.55} />
      <pointLight position={[4, 4, 4]} intensity={1.4} color={color} />
      <directionalLight position={[3, 5, 2]} intensity={1.6} />

      {/* animated starfield (rotates + twinkles) */}
      <group ref={starGroupRef}>
        <Stars radius={110} depth={45} count={3200} factor={4} saturation={0.6} fade speed={2} />
        <Stars radius={65} depth={35} count={1200} factor={2.5} saturation={0.4} fade speed={1.6} />
      </group>

      {/* slow-drifting particle trail */}
      <group ref={trailRef}>
        <Points positions={trailPositions}>
          <PointMaterial transparent color="#38bdf8" size={0.05} sizeAttenuation depthWrite={false} opacity={0.7} />
        </Points>
      </group>

      {/* core */}
      <Sphere ref={coreRef} args={[1.35, 96, 96]}>
        <MeshDistortMaterial
          color={color}
          envMapIntensity={1.4}
          clearcoat={1}
          clearcoatRoughness={0.08}
          metalness={0.85}
          roughness={0.12}
          distort={aiState === 'thinking' ? 0.55 : aiState === 'working' ? 0.4 : 0.22}
          speed={aiState === 'listening' || aiState === 'speaking' ? 5 : 2.4}
        />
      </Sphere>

      {/* inner glowing halo */}
      <mesh ref={outerRef}>
        <sphereGeometry args={[1.7, 48, 48]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.16} wireframe />
      </mesh>

      {/* orbital ring */}
      <mesh ref={ringRef} rotation={[Math.PI / 2.4, 0, 0]}>
        <torusGeometry args={[2.35, 0.022, 16, 120]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.9} />
      </mesh>

      {/* satellite points ring */}
      <Points ref={pointsRef} positions={ringPositions}>
        <PointMaterial transparent color="#67e8f9" size={0.045} sizeAttenuation depthWrite={false} />
      </Points>
    </>
  );
}