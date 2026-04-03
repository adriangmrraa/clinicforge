import React from 'react';
import { SurfacePath } from './SurfacePath';

export type SurfaceName = 'occlusal' | 'vestibular' | 'lingual' | 'mesial' | 'distal';
export type ToothStatus = 'healthy' | 'caries' | 'restoration' | 'extraction' | 'treatment_planned' | 'crown' | 'implant' | 'missing' | 'prosthesis' | 'root_canal';

// SVG fill colors per state — dark theme with subtle glow
const STATE_FILLS: Record<ToothStatus, { fill: string; stroke: string; glow: string }> = {
  healthy:           { fill: 'rgba(255,255,255,0.06)', stroke: 'rgba(255,255,255,0.20)', glow: '' },
  caries:            { fill: 'rgba(239,68,68,0.12)', stroke: '#ef4444', glow: 'drop-shadow(0 0 4px rgba(239,68,68,0.3))' },
  restoration:       { fill: 'rgba(59,130,246,0.12)', stroke: '#3b82f6', glow: 'drop-shadow(0 0 4px rgba(59,130,246,0.3))' },
  root_canal:        { fill: 'rgba(249,115,22,0.12)', stroke: '#f97316', glow: 'drop-shadow(0 0 4px rgba(249,115,22,0.3))' },
  crown:             { fill: 'rgba(139,92,246,0.12)', stroke: '#8b5cf6', glow: 'drop-shadow(0 0 4px rgba(139,92,246,0.3))' },
  implant:           { fill: 'rgba(99,102,241,0.12)', stroke: '#6366f1', glow: 'drop-shadow(0 0 4px rgba(99,102,241,0.3))' },
  prosthesis:        { fill: 'rgba(20,184,166,0.12)', stroke: '#14b8a6', glow: 'drop-shadow(0 0 4px rgba(20,184,166,0.3))' },
  extraction:        { fill: 'rgba(255,255,255,0.03)', stroke: 'rgba(255,255,255,0.15)', glow: '' },
  missing:           { fill: 'rgba(255,255,255,0.02)', stroke: 'rgba(255,255,255,0.10)', glow: '' },
  treatment_planned: { fill: 'rgba(234,179,8,0.12)', stroke: '#eab308', glow: 'drop-shadow(0 0 4px rgba(234,179,8,0.3))' },
};

// Surface paths for 5 individual surfaces (FDI notation)
const SURFACE_PATHS: Record<SurfaceName, string> = {
  // Occlusal (biting surface - top)
  occlusal: 'M10,10 L30,10 L27,20 L13,20 Z',
  // Vestibular (buccal/cheek side - right)
  vestibular: 'M30,10 A18,18 0 0,1 30,30 L20,27 A7,7 0 0,0 20,13 Z',
  // Lingual (palatal/tongue side - left)
  lingual: 'M10,30 A18,18 0 0,1 10,10 L20,13 A7,7 0 0,0 20,27 Z',
  // Mesial (toward midline - left in upper, right in lower)
  mesial: 'M10,10 L20,13 L20,27 L10,30 A18,18 0 0,0 10,10',
  // Distal (away from midline - right in upper, left in lower)
  distal: 'M30,30 L20,27 L20,13 L30,10 A18,18 0 0,0 30,30',
};

// Alternative simpler paths using arc segments
const SURFACE_PATHS_V2: Record<SurfaceName, string> = {
  // Occlusal - top center (biting surface)
  occlusal: 'M12,8 L28,8 L27,18 L13,18 Z',
  // Vestibular - right side (buccal)
  vestibular: 'M30,12 A18,18 0 0,1 30,28 L21,25 A6,6 0 0,0 21,15 Z',
  // Lingual - left side (palatal/tongue)
  lingual: 'M10,28 A18,18 0 0,1 10,12 L19,15 A6,6 0 0,0 19,25 Z',
  // Mesial - top-left quadrant
  mesial: 'M12,8 A18,18 0 0,0 10,20 L19,18 A6,6 0 0,1 13,14 Z',
  // Distal - bottom-right quadrant
  distal: 'M28,32 A18,18 0 0,0 20,20 L21,25 A6,6 0 0,1 27,29 Z',
};

// Even simpler: 4 quadrant approach + center occlusal
const SURFACE_PATHS_V3: Record<SurfaceName, string> = {
  // Occlusal - center circle (biting surface)
  occlusal: 'M20,20 m-7,0 a7,7 0 1,0 14,0 a7,7 0 1,0 -14,0',
  // Vestibular - right half (buccal)
  vestibular: 'M20,13 A18,18 0 0,1 38,20 A18,18 0 0,1 20,27 L20,13',
  // Lingual - left half (palatal)
  lingual: 'M20,27 A18,18 0 0,1 2,20 A18,18 0 0,1 20,13 L20,27',
  // Mesial - top half (toward midline)
  mesial: 'M13,20 A18,18 0 0,1 20,2 L20,13 A7,7 0 0,0 13,20 Z',
  // Distal - bottom half (away from midline)
  distal: 'M27,20 A18,18 0 0,1 20,38 L20,27 A7,7 0 0,0 27,20 Z',
};

interface ToothSVGProps {
  toothId: number;
  state: ToothStatus;
  isSelected: boolean;
  readOnly: boolean;
  onClick: () => void;
  justChanged: boolean;
  // Surface-specific state and handlers
  surfaceStates?: Record<SurfaceName, ToothStatus>;
  selectedSurface?: SurfaceName | null;
  onSurfaceClick?: (surface: SurfaceName) => void;
  // Surface labels for accessibility
  surfaceLabels?: Record<SurfaceName, string>;
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
  surfaceLabels,
}: ToothSVGProps) {
  const fills = STATE_FILLS[state] || STATE_FILLS.healthy;
  const isAbsent = state === 'missing' || state === 'extraction';
  
  // Determine if we're in surface selection mode
  const hasSurfaceData = surfaceStates && Object.keys(surfaceStates).length > 0;
  const isSurfaceSelectionMode = hasSurfaceData && isSelected;

  const handleSurfaceClick = (surface: SurfaceName) => (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onSurfaceClick) {
      onSurfaceClick(surface);
    }
  };

  const getSurfaceState = (surface: SurfaceName): ToothStatus => {
    if (surfaceStates && surfaceStates[surface]) {
      return surfaceStates[surface];
    }
    return state; // Default to tooth state
  };

  return (
    <svg
      viewBox="0 0 40 40"
      className={`w-[40px] h-[40px] sm:w-[44px] sm:h-[44px] shrink-0
        transition-all duration-300 ease-out
        ${readOnly ? 'cursor-default' : 'cursor-pointer hover:scale-110 active:scale-90'}
        ${isSelected && !isSurfaceSelectionMode ? 'scale-115 z-10' : ''}
        ${justChanged ? 'animate-[toothPop_0.4s_ease-out]' : ''}
      `}
      style={{ filter: fills.glow || undefined }}
      onClick={readOnly ? undefined : onClick}
    >
      {/* Selection ring — animated dash rotation */}
      {isSelected && !isSurfaceSelectionMode && (
        <circle
          cx="20" cy="20" r="19.5"
          fill="none" stroke="#3b82f6" strokeWidth="1.5"
          strokeDasharray="4,3"
          className="animate-[spin_8s_linear_infinite]"
          style={{ transformOrigin: 'center' }}
        />
      )}

      {/* 5 individual surface paths using SurfacePath component */}
      {(['occlusal', 'vestibular', 'lingual', 'mesial', 'distal'] as SurfaceName[]).map(surface => {
        const surfaceState = getSurfaceState(surface);
        const surfaceFills = STATE_FILLS[surfaceState] || STATE_FILLS.healthy;
        const isSurfaceSelected = selectedSurface === surface;
        
        return (
          <SurfacePath
            key={surface}
            pathD={SURFACE_PATHS_V3[surface]}
            surfaceName={surface}
            state={surfaceState}
            isSelected={isSurfaceSelected}
            onClick={isSurfaceSelectionMode ? handleSurfaceClick(surface) : undefined}
          />
        );
      })}

      {/* Surface selection ring when in surface mode */}
      {isSurfaceSelectionMode && selectedSurface && (
        <circle
          cx="20" cy="20" r="19.5"
          fill="none" stroke="#3b82f6" strokeWidth="1.5"
          strokeDasharray="4,3"
          className="animate-[spin_8s_linear_infinite]"
          style={{ transformOrigin: 'center' }}
        />
      )}

      {/* Cross lines */}
      <line x1="20" y1="2" x2="20" y2="13" stroke={fills.stroke} strokeWidth="0.6" opacity={isAbsent ? 0.2 : 0.4} className="transition-all duration-500" />
      <line x1="20" y1="27" x2="20" y2="38" stroke={fills.stroke} strokeWidth="0.6" opacity={isAbsent ? 0.2 : 0.4} className="transition-all duration-500" />
      <line x1="2" y1="20" x2="13" y2="20" stroke={fills.stroke} strokeWidth="0.6" opacity={isAbsent ? 0.2 : 0.4} className="transition-all duration-500" />
      <line x1="27" y1="20" x2="38" y2="20" stroke={fills.stroke} strokeWidth="0.6" opacity={isAbsent ? 0.2 : 0.4} className="transition-all duration-500" />

      {/* X overlay for extraction — animated */}
      {state === 'extraction' && (
        <g className="animate-[fadeIn_0.3s_ease-out]">
          <line x1="6" y1="6" x2="34" y2="34" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
          <line x1="34" y1="6" x2="6" y2="34" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
        </g>
      )}

      {/* Dash for missing */}
      {state === 'missing' && (
        <line x1="10" y1="20" x2="30" y2="20" stroke="rgba(255,255,255,0.3)" strokeWidth="2.5" strokeLinecap="round" className="animate-[fadeIn_0.3s_ease-out]" />
      )}
    </svg>
  );
}

export { STATE_FILLS };
export type { ToothStatus, SurfaceName };
