import { useEffect, useState, type CSSProperties } from 'react';

interface Particle {
  id: string;
  left: number;
  x: number;
  y: number;
  size: number;
  color: string;
  delay: number;
  duration: number;
  rotate: number;
  shape: 'circle' | 'square';
}

const COLORS = ['#00E5A3', '#00CC90', '#EAB308', '#FFFFFF', '#003D29', '#34D399'];

/**
 * One-shot confetti burst. Increment `trigger` to fire again.
 * Particles explode outward from the center of the parent (which must be
 * `position: relative`) and fade out over ~2s.
 */
export function Confetti({ trigger }: { trigger: number }) {
  const [particles, setParticles] = useState<Particle[]>([]);

  useEffect(() => {
    if (!trigger) return;

    const parts: Particle[] = Array.from({ length: 56 }, (_, i) => {
      const angle = Math.random() * Math.PI * 2;
      const distance = 120 + Math.random() * 260;
      return {
        id: `${trigger}-${i}`,
        left: 50 + (Math.random() - 0.5) * 24,
        x: Math.cos(angle) * distance,
        y: Math.sin(angle) * distance + 80,
        size: 6 + Math.random() * 8,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        delay: Math.random() * 0.18,
        duration: 1.4 + Math.random() * 0.8,
        rotate: Math.random() * 720 - 360,
        shape: Math.random() > 0.5 ? 'circle' : 'square',
      };
    });

    setParticles(parts);
    const timer = setTimeout(() => setParticles([]), 2600);
    return () => clearTimeout(timer);
  }, [trigger]);

  if (!particles.length) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-30 overflow-visible">
      {particles.map((p) => (
        <span
          key={p.id}
          className="confetti-particle"
          style={{
            left: `${p.left}%`,
            top: '50%',
            width: `${p.size}px`,
            height: `${p.size}px`,
            background: p.color,
            borderRadius: p.shape === 'circle' ? '50%' : '2px',
            animationDelay: `${p.delay}s`,
            animationDuration: `${p.duration}s`,
            ['--cx' as string]: `${p.x}px`,
            ['--cy' as string]: `${p.y}px`,
            ['--cr' as string]: `${p.rotate}deg`,
          } as CSSProperties}
        />
      ))}
    </div>
  );
}