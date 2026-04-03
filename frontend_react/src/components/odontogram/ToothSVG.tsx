import React from 'react';
import { SurfacePath } from './SurfacePath';
import { STATE_FILLS } from '../../constants/odontogramStates';

export type SurfaceName = 'occlusal' | 'vestibular' | 'lingual' | 'mesial' | 'distal';

/**
 * SVG paths for a 40x40 viewBox, center (20,20).
 * Outer circle R=18, inner circle r=7.
 * Diagonal cross at 45 degrees divides into 4 outer ring segments + center.
 */
export const SURFACE_PATHS: Record<SurfaceName, string> = {
  occlusal: 'M 20,13 A 7,7 0 1,0 20,27 A 7,7 0 1,0 20,13 Z',
  vestibular: 'M 7.3,7.3 A 18,18 0 0,1 32.7,7.3 L 25,15 A 7,7 0 0,0 15,15 Z',
  distal: 'M 32.7,7.3 A 18,18 0 0,1 32.7,32.7 L 25,25 A 7,7 0 0,0 25,15 Z',
  lingual: 'M 32.7,32.7 A 18,18 0 0,1 7.3,32.7 L 15,25 A 7,7 0 0,0 25,25 Z',
  mesial: 'M 7.3,32.7 A 18,18 0 0,1 7.3,7.3 L 15,15 A 7,7 0 0,0 15,25 Z',
};

const SURFACES: SurfaceName[] = ['occlusal', 'vestibular', 'lingual', 'mesial', 'distal'];

interface ToothSVGProps {
  toothId: number;
  state: string;
  isSelected: boolean;
  readOnly: boolean;
  onClick: () => void;
  justChanged?: boolean;
  surfaceStates?: Record<SurfaceName, string>;
  selectedSurface?: SurfaceName | null;
  onSurfaceClick?: (surface: SurfaceName) => void;
}

export function ToothSVG({
  toothId,
  state,
  isSelected,
  readOnly,
  onClick,
  justChanged,
  surfaceStates,
  selectedSurface,
  onSurfaceClick,
}: ToothSVGProps) {
  const fills = STATE_FILLS[state] || STATE_FILLS['healthy'];
  const isAbsent = state === 'ausente' || state === 'indicacion_extraccion';

  const getSurfaceState = (surface: SurfaceName): string => {
    return surfaceStates?.[surface] || state;
  };

  const handleSurfaceClick = (surface: SurfaceName) => (e: React.MouseEvent) => {
    e.stopPropagation();
    onSurfaceClick?.(surface);
  };

  return (
    <svg
      viewBox="0 0 40 40"
      className={`w-9 h-9 sm:w-11 sm:h-11 shrink-0
        transition-all duration-300 ease-out touch-manipulation
        ${readOnly ? 'cursor-default' : 'cursor-pointer active:scale-90'}
        ${isSelected ? 'scale-[1.2] z-10' : ''}
        ${justChanged ? 'animate-[toothPop_0.4s_ease-out]' : ''}
      `}
      style={{ filter: fills.glow || undefined }}
      onClick={readOnly ? undefined : onClick}
    >
      {/* Selection ring */}
      {isSelected && (
        <circle
          cx="20" cy="20" r="19.5"
          fill="none" stroke="#3b82f6" strokeWidth="1.5"
          strokeDasharray="4,3"
          className="animate-[spin_8s_linear_infinite]"
          style={{ transformOrigin: 'center' }}
        />
      )}

      {/* 5 surface sections */}
      {SURFACES.map(surface => (
        <SurfacePath
          key={surface}
          pathD={SURFACE_PATHS[surface]}
          surfaceName={surface}
          state={getSurfaceState(surface)}
          isSelected={selectedSurface === surface}
          onClick={!readOnly && onSurfaceClick ? handleSurfaceClick(surface) : undefined}
        />
      ))}

      {/* Structural dividers — white lines visible on dark background */}
      <line x1="7.3" y1="7.3" x2="15" y2="15" stroke="rgba(255,255,255,0.18)" strokeWidth="0.8" opacity={isAbsent ? 0.3 : 1} />
      <line x1="32.7" y1="7.3" x2="25" y2="15" stroke="rgba(255,255,255,0.18)" strokeWidth="0.8" opacity={isAbsent ? 0.3 : 1} />
      <line x1="32.7" y1="32.7" x2="25" y2="25" stroke="rgba(255,255,255,0.18)" strokeWidth="0.8" opacity={isAbsent ? 0.3 : 1} />
      <line x1="7.3" y1="32.7" x2="15" y2="25" stroke="rgba(255,255,255,0.18)" strokeWidth="0.8" opacity={isAbsent ? 0.3 : 1} />
      <circle cx="20" cy="20" r="7" fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="0.7" opacity={isAbsent ? 0.3 : 1} />
      <circle cx="20" cy="20" r="18" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="0.5" />

      {/* X overlay for extraction */}
      {(state === 'indicacion_extraccion' || state === 'extraction') && (
        <g className="animate-[fadeIn_0.3s_ease-out]">
          <line x1="6" y1="6" x2="34" y2="34" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
          <line x1="34" y1="6" x2="6" y2="34" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
        </g>
      )}

      {/* Dash for missing */}
      {(state === 'ausente' || state === 'missing') && (
        <line x1="10" y1="20" x2="30" y2="20" stroke="rgba(255,255,255,0.3)" strokeWidth="2.5" strokeLinecap="round" className="animate-[fadeIn_0.3s_ease-out]" />
      )}
    </svg>
  );
}
