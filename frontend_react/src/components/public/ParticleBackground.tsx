import React, { useRef, useEffect } from 'react';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  opacity: number;
  color: string;
  baseSpeed: number;
}

interface FloatingShape {
  x: number;
  y: number;
  size: number;
  opacity: number;
  targetOpacity: number;
  rotation: number;
  rotationSpeed: number;
  type: number; // 0-5 = different medical shapes
  fadeTimer: number;
  fadeDuration: number;
  driftX: number;
  driftY: number;
}

interface ParticleBackgroundProps {
  particleCount?: number;
  className?: string;
}

const COLORS = [
  'rgba(59, 130, 246, OPACITY)',
  'rgba(99, 102, 241, OPACITY)',
  'rgba(139, 92, 246, OPACITY)',
  'rgba(16, 185, 129, OPACITY)',
  'rgba(6, 182, 212, OPACITY)',
  'rgba(59, 130, 246, OPACITY)',
];

// Draw medical silhouette shapes on canvas
function drawMedicalShape(ctx: CanvasRenderingContext2D, type: number, x: number, y: number, size: number, opacity: number, rotation: number) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rotation);
  ctx.globalAlpha = opacity;
  ctx.strokeStyle = `rgba(59, 130, 246, ${opacity * 0.6})`;
  ctx.fillStyle = `rgba(59, 130, 246, ${opacity * 0.15})`;
  ctx.lineWidth = 1.5;

  const s = size;

  switch (type) {
    case 0: // Cross / medical plus
      ctx.beginPath();
      ctx.roundRect(-s * 0.15, -s * 0.5, s * 0.3, s, s * 0.06);
      ctx.roundRect(-s * 0.5, -s * 0.15, s, s * 0.3, s * 0.06);
      ctx.fill();
      ctx.stroke();
      break;

    case 1: // Tooth silhouette
      ctx.beginPath();
      ctx.moveTo(0, -s * 0.5);
      ctx.bezierCurveTo(s * 0.35, -s * 0.5, s * 0.4, -s * 0.15, s * 0.3, s * 0.1);
      ctx.bezierCurveTo(s * 0.25, s * 0.3, s * 0.2, s * 0.5, s * 0.1, s * 0.5);
      ctx.bezierCurveTo(s * 0.05, s * 0.5, 0.05 * s, s * 0.35, 0, s * 0.3);
      ctx.bezierCurveTo(-0.05 * s, s * 0.35, -s * 0.05, s * 0.5, -s * 0.1, s * 0.5);
      ctx.bezierCurveTo(-s * 0.2, s * 0.5, -s * 0.25, s * 0.3, -s * 0.3, s * 0.1);
      ctx.bezierCurveTo(-s * 0.4, -s * 0.15, -s * 0.35, -s * 0.5, 0, -s * 0.5);
      ctx.fill();
      ctx.stroke();
      break;

    case 2: // Heart / pulse
      ctx.beginPath();
      ctx.moveTo(0, s * 0.35);
      ctx.bezierCurveTo(-s * 0.05, s * 0.3, -s * 0.4, s * 0.05, -s * 0.4, -s * 0.15);
      ctx.bezierCurveTo(-s * 0.4, -s * 0.4, -s * 0.1, -s * 0.45, 0, -s * 0.25);
      ctx.bezierCurveTo(s * 0.1, -s * 0.45, s * 0.4, -s * 0.4, s * 0.4, -s * 0.15);
      ctx.bezierCurveTo(s * 0.4, s * 0.05, s * 0.05, s * 0.3, 0, s * 0.35);
      ctx.fill();
      ctx.stroke();
      break;

    case 3: // Stethoscope circle
      ctx.beginPath();
      ctx.arc(0, 0, s * 0.35, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(0, 0, s * 0.15, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      // Tube line
      ctx.beginPath();
      ctx.moveTo(0, -s * 0.35);
      ctx.bezierCurveTo(-s * 0.3, -s * 0.6, -s * 0.5, -s * 0.3, -s * 0.3, -s * 0.5);
      ctx.stroke();
      break;

    case 4: // DNA helix dots
      for (let i = 0; i < 8; i++) {
        const angle = (i / 8) * Math.PI * 2;
        const px = Math.sin(angle) * s * 0.3;
        const py = (i / 8 - 0.5) * s;
        ctx.beginPath();
        ctx.arc(px, py, s * 0.04, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(-px, py, s * 0.04, 0, Math.PI * 2);
        ctx.fill();
        // Connect
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(-px, py);
        ctx.stroke();
      }
      break;

    case 5: // Shield / protection
      ctx.beginPath();
      ctx.moveTo(0, -s * 0.45);
      ctx.lineTo(s * 0.4, -s * 0.25);
      ctx.lineTo(s * 0.35, s * 0.15);
      ctx.bezierCurveTo(s * 0.25, s * 0.4, 0, s * 0.5, 0, s * 0.5);
      ctx.bezierCurveTo(0, s * 0.5, -s * 0.25, s * 0.4, -s * 0.35, s * 0.15);
      ctx.lineTo(-s * 0.4, -s * 0.25);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      break;
  }

  ctx.restore();
}

function createShape(w: number, h: number): FloatingShape {
  return {
    x: Math.random() * w,
    y: Math.random() * h,
    size: 60 + Math.random() * 120,
    opacity: 0,
    targetOpacity: 0.04 + Math.random() * 0.06,
    rotation: Math.random() * Math.PI * 2,
    rotationSpeed: (Math.random() - 0.5) * 0.003,
    type: Math.floor(Math.random() * 6),
    fadeTimer: 0,
    fadeDuration: 3000 + Math.random() * 5000,
    driftX: (Math.random() - 0.5) * 0.15,
    driftY: (Math.random() - 0.5) * 0.1,
  };
}

export default function ParticleBackground({ particleCount = 60, className = '' }: ParticleBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const particlesRef = useRef<Particle[]>([]);
  const shapesRef = useRef<FloatingShape[]>([]);
  const rafRef = useRef<number>(0);
  const timeRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;

    // Init particles — FASTER, BIGGER, more visible
    particlesRef.current = Array.from({ length: particleCount }, () => {
      const speed = 0.3 + Math.random() * 1.2;
      const angle = Math.random() * Math.PI * 2;
      return {
        x: Math.random() * w,
        y: Math.random() * h,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: 1 + Math.random() * 3,
        opacity: 0.2 + Math.random() * 0.6,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        baseSpeed: speed,
      };
    });

    // Init floating medical shapes (4-6 visible at a time, cycling)
    shapesRef.current = Array.from({ length: 8 }, () => {
      const shape = createShape(w, h);
      shape.fadeTimer = Math.random() * shape.fadeDuration; // stagger
      return shape;
    });

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    const handleTouchMove = (e: TouchEvent) => {
      const rect = canvas.getBoundingClientRect();
      const touch = e.touches[0];
      mouseRef.current = { x: touch.clientX - rect.left, y: touch.clientY - rect.top };
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('touchmove', handleTouchMove, { passive: true });

    let lastTime = performance.now();

    const animate = (now: number) => {
      const dt = Math.min(now - lastTime, 50); // cap delta
      lastTime = now;
      timeRef.current += dt;

      const cw = canvas.offsetWidth;
      const ch = canvas.offsetHeight;
      ctx.clearRect(0, 0, cw, ch);

      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;
      const particles = particlesRef.current;
      const shapes = shapesRef.current;
      const connectionDistance = 150;
      const mouseRadius = 200;

      // ── Draw floating medical shapes (background layer) ──
      for (const shape of shapes) {
        shape.fadeTimer += dt;
        shape.x += shape.driftX;
        shape.y += shape.driftY;
        shape.rotation += shape.rotationSpeed;

        // Fade cycle: in → hold → out → wait → restart
        const cycle = shape.fadeDuration;
        const phase = (shape.fadeTimer % (cycle * 3)) / cycle;

        if (phase < 1) {
          // Fade in
          shape.opacity = shape.targetOpacity * (phase);
        } else if (phase < 2) {
          // Hold
          shape.opacity = shape.targetOpacity;
        } else {
          // Fade out
          shape.opacity = shape.targetOpacity * (3 - phase);
        }

        // Reset position if drifted off screen
        if (shape.x < -shape.size || shape.x > cw + shape.size || shape.y < -shape.size || shape.y > ch + shape.size) {
          Object.assign(shape, createShape(cw, ch));
          shape.fadeTimer = 0;
        }

        if (shape.opacity > 0.005) {
          drawMedicalShape(ctx, shape.type, shape.x, shape.y, shape.size, shape.opacity, shape.rotation);
        }
      }

      // ── Draw particles ──
      ctx.globalAlpha = 1;
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        // Mouse interaction — stronger
        const dmx = mx - p.x;
        const dmy = my - p.y;
        const distMouse = Math.sqrt(dmx * dmx + dmy * dmy);
        if (distMouse < mouseRadius && distMouse > 0) {
          const force = (mouseRadius - distMouse) / mouseRadius;
          p.vx += (dmx / distMouse) * force * 0.08;
          p.vy += (dmy / distMouse) * force * 0.08;
        }

        // Light friction (keeps them moving)
        p.vx *= 0.995;
        p.vy *= 0.995;

        // Ensure minimum speed
        const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
        if (speed < p.baseSpeed * 0.3) {
          const angle = Math.atan2(p.vy, p.vx);
          p.vx = Math.cos(angle) * p.baseSpeed * 0.3;
          p.vy = Math.sin(angle) * p.baseSpeed * 0.3;
        }

        p.x += p.vx;
        p.y += p.vy;

        // Wrap
        if (p.x < -10) p.x = cw + 10;
        if (p.x > cw + 10) p.x = -10;
        if (p.y < -10) p.y = ch + 10;
        if (p.y > ch + 10) p.y = -10;

        // Draw particle (bigger, brighter)
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color.replace('OPACITY', String(p.opacity));
        ctx.fill();

        // Mouse glow
        if (distMouse < mouseRadius) {
          const glowOpacity = ((mouseRadius - distMouse) / mouseRadius) * 0.5;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size * 4, 0, Math.PI * 2);
          ctx.fillStyle = p.color.replace('OPACITY', String(glowOpacity * 0.3));
          ctx.fill();
        }

        // Connection lines
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < connectionDistance) {
            const lineOpacity = (1 - dist / connectionDistance) * 0.2;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(99, 130, 246, ${lineOpacity})`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }

      // Mouse connection lines
      if (mx > 0 && my > 0) {
        for (const p of particles) {
          const dx = mx - p.x;
          const dy = my - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < mouseRadius) {
            const lineOpacity = (1 - dist / mouseRadius) * 0.35;
            ctx.beginPath();
            ctx.moveTo(mx, my);
            ctx.lineTo(p.x, p.y);
            ctx.strokeStyle = `rgba(59, 130, 246, ${lineOpacity})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('touchmove', handleTouchMove);
    };
  }, [particleCount]);

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 w-full h-full ${className}`}
      style={{ zIndex: 0 }}
    />
  );
}
