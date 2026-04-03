import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { SurfacePath, type ToothStatus } from './SurfacePath';
import { SurfaceName } from './ToothSVG';

// Enlarged surface paths for mobile zoom (3x scale from 40px to 120px)
const ZOOM_SURFACE_PATHS: Record<SurfaceName, string> = {
  occlusal: 'M60,60 m-21,0 a21,21 0 1,0 42,0 a21,21 0 1,0 -42,0',
  vestibular: 'M60,39 A54,54 0 0,1 114,60 A54,54 0 0,1 60,81 L60,39',
  lingual: 'M60,81 A54,54 0 0,1 6,60 A54,54 0 0,1 60,39 L60,81',
  mesial: 'M39,60 A54,54 0 0,1 60,6 L60,39 A21,21 0 0,0 39,60 Z',
  distal: 'M81,60 A54,54 0 0,1 60,114 L60,81 A21,21 0 0,0 81,60 Z',
};

interface MobileToothZoomProps {
  toothId: number;
  toothState: ToothStatus;
  surfaceStates?: Record<SurfaceName, ToothStatus>;
  selectedSurface: SurfaceName | null;
  onSurfaceClick: (surface: SurfaceName) => void;
  onClose: () => void;
  triggerRef: React.RefObject<HTMLDivElement | null>;
}

export function MobileToothZoom({
  toothId,
  toothState,
  surfaceStates,
  selectedSurface,
  onSurfaceClick,
  onClose,
  triggerRef,
}: MobileToothZoomProps) {
  const { t } = useTranslation();
  const modalRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const [isVisible, setIsVisible] = useState(false);

  // Get position from trigger element
  useEffect(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      // Position above the tooth, centered horizontally
      const newTop = rect.top - 280; // 120px height + padding
      const newLeft = rect.left + rect.width / 2 - 60; // Center on tooth
      
      setPosition({
        top: Math.max(10, newTop), // Keep within viewport
        left: Math.max(10, Math.min(newLeft, window.innerWidth - 130)),
      });
    }
  }, [triggerRef]);

  // Animate in
  useEffect(() => {
    requestAnimationFrame(() => {
      setIsVisible(true);
    });
  }, []);

  // Handle click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        handleClose();
      }
    };

    // Slight delay to prevent immediate close on open
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
    setTimeout(onClose, 200); // Wait for animation
  };

  const handleSurfaceClick = (surface: SurfaceName) => (e: React.MouseEvent) => {
    e.stopPropagation();
    onSurfaceClick(surface);
  };

  // Get state for each surface
  const getSurfaceState = (surface: SurfaceName): ToothStatus => {
    if (surfaceStates && surfaceStates[surface]) {
      return surfaceStates[surface];
    }
    return toothState;
  };

  // Surface labels with translations
  const surfaceLabels: Record<SurfaceName, string> = {
    occlusal: t('odontogram.surfaces.occlusal'),
    vestibular: t('odontogram.surfaces.vestibular'),
    lingual: t('odontogram.surfaces.lingual'),
    mesial: t('odontogram.surfaces.mesial'),
    distal: t('odontogram.surfaces.distal'),
  };

  return (
    <div
      ref={modalRef}
      className={`
        fixed z-50 transition-all duration-300 ease-out
        ${isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-90 pointer-events-none'}
      `}
      style={{
        top: position.top,
        left: position.left,
        width: 120,
        height: 120,
      }}
    >
      {/* Modal container */}
      <div className="relative w-full h-full">
        {/* Background */}
        <div className="absolute inset-0 bg-[#0d1117]/95 backdrop-blur-xl rounded-2xl border border-white/[0.10] shadow-2xl" />
        
        {/* Tooth ID label */}
        <div className="absolute -top-7 left-1/2 -translate-x-1/2 text-[10px] font-bold text-white/60">
          {Math.floor(toothId / 10)}.{toothId % 10}
        </div>

        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute -top-3 -right-3 w-6 h-6 rounded-full bg-red-500/20 border border-red-500/40 text-red-400 text-xs flex items-center justify-center hover:bg-red-500/30 transition-colors z-10"
        >
          ×
        </button>

        {/* SVG Surface buttons */}
        <svg
          viewBox="0 0 120 120"
          className="w-full h-full p-2"
        >
          {(['occlusal', 'vestibular', 'lingual', 'mesial', 'distal'] as SurfaceName[]).map(surface => {
            const surfaceState = getSurfaceState(surface);
            const isSurfaceSelected = selectedSurface === surface;
            
            return (
              <g key={surface} onClick={handleSurfaceClick(surface)} className="cursor-pointer">
                <SurfacePath
                  pathD={ZOOM_SURFACE_PATHS[surface]}
                  surfaceName={surface}
                  state={surfaceState}
                  isSelected={isSurfaceSelected}
                  onClick={() => {}}
                />
                {/* Surface label */}
                {isSurfaceSelected && (
                  <text
                    x="60"
                    y="115"
                    textAnchor="middle"
                    className="fill-white/80 text-[8px] font-bold"
                  >
                    {surfaceLabels[surface]}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Instructions */}
        <div className="absolute bottom-[-28px] left-1/2 -translate-x-1/2 text-[9px] text-white/40 whitespace-nowrap">
          {t('odontogram.mobile_tap_surface')}
        </div>
      </div>
    </div>
  );
}

export default MobileToothZoom;