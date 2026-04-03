import React from 'react';

type ToothStatus = 'healthy' | 'caries' | 'restoration' | 'extraction' | 'treatment_planned' | 'crown' | 'implant' | 'missing' | 'prosthesis' | 'root_canal';

interface SurfacePathProps {
  pathD: string;
  surfaceName: string;
  state: ToothStatus;
  condition?: string;
  color?: string;
  isSelected: boolean;
  onClick?: () => void;
}

// Default colors per state
const DEFAULT_COLORS: Record<ToothStatus, { fill: string; stroke: string }> = {
  healthy:           { fill: 'rgba(255,255,255,0.06)', stroke: 'rgba(255,255,255,0.20)' },
  caries:            { fill: 'rgba(239,68,68,0.12)', stroke: '#ef4444' },
  restoration:       { fill: 'rgba(59,130,246,0.12)', stroke: '#3b82f6' },
  root_canal:        { fill: 'rgba(249,115,22,0.12)', stroke: '#f97316' },
  crown:             { fill: 'rgba(139,92,246,0.12)', stroke: '#8b5cf6' },
  implant:           { fill: 'rgba(99,102,241,0.12)', stroke: '#6366f1' },
  prosthesis:        { fill: 'rgba(20,184,166,0.12)', stroke: '#14b8a6' },
  extraction:        { fill: 'rgba(255,255,255,0.03)', stroke: 'rgba(255,255,255,0.15)' },
  missing:           { fill: 'rgba(255,255,255,0.02)', stroke: 'rgba(255,255,255,0.10)' },
  treatment_planned: { fill: 'rgba(234,179,8,0.12)', stroke: '#eab308' },
};

export function SurfacePath({
  pathD,
  surfaceName,
  state,
  condition,
  color,
  isSelected,
  onClick,
}: SurfacePathProps) {
  // Color priority: custom → default_color → healthy
  const defaultColor = DEFAULT_COLORS[state] || DEFAULT_COLORS.healthy;
  const fill = color || defaultColor.fill;
  const stroke = defaultColor.stroke;
  const isAbsent = state === 'missing' || state === 'extraction';

  return (
    <path
      d={pathD}
      fill={fill}
      stroke={stroke}
      strokeWidth={isSelected ? '2' : '1'}
      opacity={isAbsent ? 0.35 : 0.9}
      className={`
        transition-all duration-300
        ${onClick ? 'cursor-pointer' : ''}
        hover:scale-[1.05] hover:opacity-100
        ${isSelected ? 'drop-shadow-[0_0_6px_rgba(59,130,246,0.5)]' : ''}
      `}
      style={isSelected ? { strokeWidth: 2 } : undefined}
      onClick={onClick}
    />
  );
}

export type { ToothStatus };
