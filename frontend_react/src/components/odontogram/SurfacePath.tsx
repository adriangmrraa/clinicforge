import React from 'react';
import { STATE_FILLS } from '../../constants/odontogramStates';

interface SurfacePathProps {
  pathD: string;
  surfaceName: string;
  state: string;
  color?: string;
  isSelected: boolean;
  onClick?: () => void;
}

export function SurfacePath({
  pathD,
  surfaceName,
  state,
  color,
  isSelected,
  onClick,
}: SurfacePathProps) {
  const fills = STATE_FILLS[state] || STATE_FILLS['healthy'];
  const fill = color || fills.fill;
  const stroke = fills.stroke;
  const isAbsent = state === 'ausente' || state === 'indicacion_extraccion' || state === 'missing' || state === 'extraction';

  return (
    <path
      d={pathD}
      fill={fill}
      stroke={stroke}
      strokeWidth={isSelected ? '1.8' : '0.8'}
      opacity={isAbsent ? 0.35 : 0.9}
      className={`
        transition-all duration-200
        ${onClick ? 'cursor-pointer hover:opacity-100 hover:brightness-125' : ''}
        ${isSelected ? 'drop-shadow-[0_0_6px_rgba(59,130,246,0.5)]' : ''}
      `}
      onClick={onClick}
    />
  );
}
