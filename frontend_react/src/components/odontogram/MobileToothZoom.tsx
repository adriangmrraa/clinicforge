import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { SurfacePath } from './SurfacePath';
import { type SurfaceName } from './ToothSVG';
import { STATE_FILLS } from '../../constants/odontogramStates';

/**
 * 3x scale of SURFACE_PATHS (120x120 viewBox, center 60,60)
 * Outer R=54, inner r=21, diagonal cross at 45 degrees.
 */
const ZOOM_SURFACE_PATHS: Record<SurfaceName, string> = {
  occlusal:   'M 60,39 A 21,21 0 1,0 60,81 A 21,21 0 1,0 60,39 Z',
  vestibular: 'M 22,22 A 54,54 0 0,1 98,22 L 75,45 A 21,21 0 0,0 45,45 Z',
  distal:     'M 98,22 A 54,54 0 0,1 98,98 L 75,75 A 21,21 0 0,0 75,45 Z',
  lingual:    'M 98,98 A 54,54 0 0,1 22,98 L 45,75 A 21,21 0 0,0 75,75 Z',
  mesial:     'M 22,98 A 54,54 0 0,1 22,22 L 45,45 A 21,21 0 0,0 45,75 Z',
};

const SURFACES: SurfaceName[] = ['occlusal', 'vestibular', 'lingual', 'mesial', 'distal'];

interface MobileToothZoomProps {
  toothId: number;
  toothState: string;
  surfaceStates?: Record<SurfaceName, string>;
  selectedSurface: SurfaceName | null;
  onSurfaceClick: (surface: SurfaceName) => void;
  onClose: () => void;
}

export function MobileToothZoom({
  toothId,
  toothState,
  surfaceStates,
  selectedSurface,
  onSurfaceClick,
  onClose,
}: MobileToothZoomProps) {
  const { t } = useTranslation();
  const modalRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setIsVisible(true));
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        handleClose();
      }
    };
    const timer = setTimeout(() => {
      document.addEventListener('click', handleClickOutside);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('click', handleClickOutside);
    };
  }, []);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(onClose, 200);
  };

  const getSurfaceState = (surface: SurfaceName): string => {
    return surfaceStates?.[surface] || toothState;
  };

  const fills = STATE_FILLS[toothState] || STATE_FILLS['healthy'];

  return (
    <div
      ref={modalRef}
      className={`
        bg-[#0d1117]/95 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl p-3
        transition-all duration-200 ease-out
        ${isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-90 pointer-events-none'}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-white">
          {t('odontogram.piece')} {Math.floor(toothId / 10)}.{toothId % 10}
        </span>
        <button
          onClick={handleClose}
          className="w-6 h-6 rounded-full bg-white/5 text-white/40 text-xs flex items-center justify-center hover:bg-white/10"
        >
          x
        </button>
      </div>

      {/* Zoomed SVG */}
      <svg viewBox="0 0 120 120" className="w-[140px] h-[140px] mx-auto">
        {SURFACES.map(surface => (
          <SurfacePath
            key={surface}
            pathD={ZOOM_SURFACE_PATHS[surface]}
            surfaceName={surface}
            state={getSurfaceState(surface)}
            isSelected={selectedSurface === surface}
            onClick={() => onSurfaceClick(surface)}
          />
        ))}
        {/* Diagonal cross dividers */}
        <line x1="22" y1="22" x2="45" y2="45" stroke={fills.stroke} strokeWidth="1" opacity="0.3" />
        <line x1="98" y1="22" x2="75" y2="45" stroke={fills.stroke} strokeWidth="1" opacity="0.3" />
        <line x1="98" y1="98" x2="75" y2="75" stroke={fills.stroke} strokeWidth="1" opacity="0.3" />
        <line x1="22" y1="98" x2="45" y2="75" stroke={fills.stroke} strokeWidth="1" opacity="0.3" />
      </svg>

      <p className="text-[10px] text-white/40 text-center mt-1">
        {t('odontogram.tap_surface')}
      </p>
    </div>
  );
}

export default MobileToothZoom;
