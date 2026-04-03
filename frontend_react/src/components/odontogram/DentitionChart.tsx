import React from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { ToothSVG, type SurfaceName, type ToothStatus } from './ToothSVG';

export type DentitionType = 'permanent' | 'deciduous';

export interface QuadrantsConfig {
  upperRight: number[];
  upperLeft: number[];
  lowerRight: number[];
  lowerLeft: number[];
}

// FDI notation quadrants for permanent teeth (8 per quadrant)
export const PERMANENT_QUADRANTS: QuadrantsConfig = {
  upperRight: [18, 17, 16, 15, 14, 13, 12, 11],
  upperLeft: [21, 22, 23, 24, 25, 26, 27, 28],
  lowerRight: [48, 47, 46, 45, 44, 43, 42, 41],
  lowerLeft: [31, 32, 33, 34, 35, 36, 37, 38],
};

// FDI notation quadrants for deciduous teeth (5 per quadrant)
export const DECIDUOUS_QUADRANTS: QuadrantsConfig = {
  upperRight: [55, 54, 53, 52, 51],
  upperLeft: [61, 62, 63, 64, 65],
  lowerRight: [85, 84, 83, 82, 81],
  lowerLeft: [71, 72, 73, 74, 75],
};

export interface ToothState {
  id: number;
  state: ToothStatus;
  surfaces?: Record<SurfaceName, ToothStatus>;
  notes?: string;
}

export interface DentitionChartProps {
  teeth: ToothState[];
  quadrantsConfig: QuadrantsConfig;
  onToothClick: (toothId: number) => void;
  onSurfaceClick?: (toothId: number, surface: SurfaceName) => void;
  selectedTooth: number | null;
  selectedSurface: SurfaceName | null;
  readOnly: boolean;
  changedTeeth?: Set<number>;
}

// Helper to get FDI label
function fdiLabel(id: number): string {
  return `${Math.floor(id / 10)}.${id % 10}`;
}

export function DentitionChart({
  teeth,
  quadrantsConfig,
  onToothClick,
  onSurfaceClick,
  selectedTooth,
  selectedSurface,
  readOnly,
  changedTeeth = new Set(),
}: DentitionChartProps) {
  const { t } = useTranslation();

  // Render a row of teeth with numbers
  const renderTeethRow = (ids: number[], numbersBelow: boolean, isUpper: boolean) => (
    <div className="flex gap-[2px] sm:gap-1">
      {ids.map(id => {
        const tooth = teeth.find(t => t.id === id);
        const state = (tooth?.state || 'healthy') as ToothStatus;
        const isSelected = selectedTooth === id;
        const justChanged = changedTeeth.has(id);
        const label = fdiLabel(id);
        
        // Get surface states if available
        const surfaceStates = tooth?.surfaces;

        return (
          <div 
            key={id} 
            className="flex flex-col items-center"
            data-tooth-id={id}
          >
            {!numbersBelow && (
              <span className={`text-[9px] sm:text-[10px] font-bold mb-0.5 select-none transition-colors duration-200 ${isSelected ? 'text-blue-400' : 'text-white/40'}`}>
                {label}
              </span>
            )}
            <ToothSVG
              toothId={id}
              state={state}
              isSelected={isSelected}
              readOnly={readOnly}
              onClick={() => onToothClick(id)}
              justChanged={justChanged}
              surfaceStates={surfaceStates}
              selectedSurface={selectedSurface}
              onSurfaceClick={onSurfaceClick ? (surface) => onSurfaceClick(id, surface) : undefined}
            />
            {numbersBelow && (
              <span className={`text-[9px] sm:text-[10px] font-bold mt-0.5 select-none transition-colors duration-200 ${isSelected ? 'text-blue-400' : 'text-white/40'}`}>
                {label}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max mx-auto flex flex-col items-center gap-0">
        {/* Upper jaw */}
        <div className="flex gap-1 sm:gap-2">
          {renderTeethRow(quadrantsConfig.upperRight, false, true)}
          <div className="w-px bg-white/[0.08] mx-1 self-stretch" />
          {renderTeethRow(quadrantsConfig.upperLeft, false, true)}
        </div>

        {/* Jaw separator */}
        <div className="w-full max-w-md my-2">
          <div className="h-[2px] bg-white/[0.10] rounded-full" />
        </div>

        {/* Lower jaw */}
        <div className="flex gap-1 sm:gap-2">
          {renderTeethRow(quadrantsConfig.lowerRight, true, false)}
          <div className="w-px bg-white/[0.08] mx-1 self-stretch" />
          {renderTeethRow(quadrantsConfig.lowerLeft, true, false)}
        </div>
      </div>
    </div>
  );
}

// Helper hook to get appropriate quadrant config
export function useQuadrantsConfig(dentitionType: DentitionType): QuadrantsConfig {
  return dentitionType === 'permanent' ? PERMANENT_QUADRANTS : DECIDUOUS_QUADRANTS;
}