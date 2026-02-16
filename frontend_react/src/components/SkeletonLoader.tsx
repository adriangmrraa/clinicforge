import React from 'react';

// ==================== SKELETON LOADER TYPES ====================

interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rectangular' | 'tooth' | 'calendar' | 'avatar';
  width?: string | number;
  height?: string | number;
  animation?: 'pulse' | 'wave' | 'none';
  className?: string;
}

// ==================== BASE SKELETON COMPONENT ====================

const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'text',
  width,
  height,
  animation = 'pulse',
  className = '',
}) => {
  const baseStyles = 'bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 bg-[length:200%_100%]';
  
  const variantStyles = {
    text: 'rounded h-4',
    circular: 'rounded-full',
    rectangular: 'rounded-lg',
    tooth: 'rounded-sm',
    calendar: 'rounded-md',
    avatar: 'rounded-full',
  };
  
  const animationStyles = {
    pulse: 'animate-pulse',
    wave: 'animate-[shimmer_1.5s_infinite]',
    none: '',
  };
  
  const style: React.CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  };
  
  return (
    <div
      className={`${baseStyles} ${variantStyles[variant]} ${animationStyles[animation]} ${className}`}
      style={style}
    />
  );
};

// ==================== MEDICAL SKELETONS ====================

// Tooth-shaped skeleton for dental content
export const ToothSkeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`relative ${className}`}>
    <div className="w-12 h-16 bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 rounded-sm animate-pulse relative overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-8 bg-white/30 rounded-sm" />
    </div>
  </div>
);

// Calendar day skeleton for agenda
export const CalendarDaySkeleton: React.FC<{ hasEvent?: boolean }> = ({ hasEvent = false }) => (
  <div className="p-2 border border-gray-100 rounded-lg">
    <Skeleton variant="text" width="60%" height={12} className="mb-2" />
    {hasEvent && (
      <div className="space-y-1">
        <Skeleton variant="rectangular" width="100%" height={8} />
        <Skeleton variant="rectangular" width="80%" height={8} />
      </div>
    )}
  </div>
);

// Patient card skeleton
export const PatientCardSkeleton: React.FC = () => (
  <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
    <div className="flex items-center gap-4">
      <Skeleton variant="avatar" width={48} height={48} />
      <div className="flex-1 space-y-2">
        <Skeleton variant="text" width="60%" height={16} />
        <Skeleton variant="text" width="40%" height={12} />
      </div>
    </div>
    <div className="mt-4 flex gap-2">
      <Skeleton variant="rectangular" width={80} height={24} className="rounded-full" />
      <Skeleton variant="rectangular" width={80} height={24} className="rounded-full" />
    </div>
  </div>
);

// Agenda event skeleton
export const AgendaEventSkeleton: React.FC = () => (
  <div className="p-3 rounded-lg border border-gray-100 mb-2">
    <div className="flex items-center gap-3">
      <div className="w-1 h-12 rounded-full bg-gradient-to-b from-blue-400 to-blue-600" />
      <div className="flex-1 space-y-2">
        <Skeleton variant="text" width="70%" height={14} />
        <Skeleton variant="text" width="50%" height={12} />
      </div>
    </div>
  </div>
);

// Chat message skeleton
export const ChatMessageSkeleton: React.FC<{ isUser?: boolean }> = ({ isUser = false }) => (
  <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
    <Skeleton variant="circular" width={32} height={32} />
    <div className={`max-w-[70%] space-y-2 ${isUser ? 'items-end' : 'items-start'}`}>
      <div className={`${isUser ? 'bg-blue-100' : 'bg-gray-100'} p-3 rounded-2xl rounded-${isUser ? 'tl-none' : 'tr-none'}`}>
        <Skeleton variant="text" width={120} height={12} />
        <Skeleton variant="text" width={80} height={12} className="mt-1" />
      </div>
    </div>
  </div>
);

// Stats card skeleton
export const StatsCardSkeleton: React.FC = () => (
  <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
    <div className="flex items-center justify-between mb-4">
      <Skeleton variant="circular" width={48} height={48} />
      <Skeleton variant="text" width={60} height={24} />
    </div>
    <Skeleton variant="text" width="80%" height={32} />
    <Skeleton variant="text" width="50%" height={14} className="mt-2" />
  </div>
);

// Form field skeleton
export const FormFieldSkeleton: React.FC = () => (
  <div className="space-y-2">
    <Skeleton variant="text" width={100} height={14} />
    <Skeleton variant="rectangular" width="100%" height={40} />
  </div>
);

// Table row skeleton
export const TableRowSkeleton: React.FC<{ columns: number }> = ({ columns }) => (
  <tr className="border-b border-gray-50">
    {Array.from({ length: columns }).map((_, i) => (
      <td key={i} className="px-4 py-3">
        <Skeleton variant="text" width="80%" height={16} />
      </td>
    ))}
  </tr>
);

// Professional avatar skeleton
export const ProfessionalAvatarSkeleton: React.FC = () => (
  <div className="flex items-center gap-3 p-3">
    <Skeleton variant="circular" width={56} height={56} />
    <div className="space-y-2">
      <Skeleton variant="text" width={150} height={18} />
      <Skeleton variant="text" width={100} height={14} />
    </div>
  </div>
);

// ==================== LOADING SCREENS ====================

// Full page loading with dental theme
export const PageLoader: React.FC<{ message?: string }> = ({ message = 'Cargando...' }) => (
  <div className="min-h-[400px] flex flex-col items-center justify-center p-8">
    <div className="relative mb-6">
      {/* Rotating tooth animation */}
      <div className="w-16 h-16 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <svg className="w-8 h-8 text-primary" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C9.5 2 7 4.5 7 7c0 1.5.5 2.5 1.5 3.5L7 14c0 1.5 1 3 2.5 3h5c1.5 0 2.5-1.5 2.5-3l-1.5-3.5C16.5 9.5 17 8.5 17 7c0-2.5-2.5-5-5-5zm0 2c1.5 0 3 1 3 2.5 0 .5-.5 1.5-1.5 2.5h-3C.5 89 9 7 9 6.5 9 5 10.5 4 12 4z" />
        </svg>
      </div>
    </div>
    <p className="text-gray-500 font-medium">{message}</p>
    <div className="mt-4 flex gap-1">
      <span className="w-2 h-2 bg-primary rounded-full animate-bounce [animation-delay:0s]" />
      <span className="w-2 h-2 bg-primary rounded-full animate-bounce [animation-delay:0.1s]" />
      <span className="w-2 h-2 bg-primary rounded-full animate-bounce [animation-delay:0.2s]" />
    </div>
  </div>
);

// Card grid loader
export const CardGridSkeleton: React.FC<{ count?: number }> = ({ count = 4 }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {Array.from({ length: count }).map((_, i) => (
      <PatientCardSkeleton key={i} />
    ))}
  </div>
);

// Chat list loader
export const ChatListSkeleton: React.FC = () => (
  <div className="space-y-3">
    {Array.from({ length: 5 }).map((_, i) => (
      <div key={i} className="flex items-center gap-3 p-3">
        <Skeleton variant="circular" width={48} height={48} />
        <div className="flex-1 space-y-2">
          <div className="flex justify-between">
            <Skeleton variant="text" width={120} height={14} />
            <Skeleton variant="text" width={40} height={12} />
          </div>
          <Skeleton variant="text" width="80%" height={12} />
        </div>
      </div>
    ))}
  </div>
);

// ==================== UTILITY ====================

export default Skeleton;
