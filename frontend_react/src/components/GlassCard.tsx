import React, { useState } from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  image?: string;
  className?: string;
  hoverScale?: boolean;
  onClick?: () => void;
}

/**
 * Reusable glass card with optional background image that fades in on hover/touch.
 * Same aesthetic as Sidebar items: subtle image, scale-up animation, glassmorphism.
 */
const GlassCard: React.FC<GlassCardProps> = ({
  children,
  image,
  className = '',
  hoverScale = true,
  onClick,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-white/[0.06] transition-all duration-300 ease-out group ${onClick ? 'cursor-pointer' : ''} ${className}`}
      style={{
        transform: isHovered && hoverScale ? 'scale(1.02)' : 'scale(1)',
        transition: 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease',
        boxShadow: isHovered ? '0 8px 32px rgba(0,0,0,0.3)' : 'none',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onTouchStart={() => setIsHovered(true)}
      onTouchEnd={() => setTimeout(() => setIsHovered(false), 400)}
      onClick={onClick}
    >
      {/* Background image — fades in on hover */}
      {image && (
        <div
          className="absolute inset-0 bg-cover bg-center transition-opacity duration-500 ease-out pointer-events-none"
          style={{
            backgroundImage: `url(${image})`,
            opacity: isHovered ? 0.1 : 0,
          }}
        />
      )}

      {/* Glass overlay */}
      <div className={`absolute inset-0 transition-all duration-300 pointer-events-none ${
        isHovered ? 'bg-white/[0.04]' : 'bg-white/[0.02]'
      }`} />

      {/* Subtle gradient edge on hover */}
      {isHovered && (
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/[0.04] to-transparent pointer-events-none" />
      )}

      {/* Hover ring */}
      {isHovered && (
        <div className="absolute inset-0 rounded-2xl ring-1 ring-white/[0.1] pointer-events-none" />
      )}

      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
};

export default GlassCard;

// Pre-defined images for different contexts
export const CARD_IMAGES = {
  revenue: 'https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=400&q=60',
  appointments: 'https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=400&q=60',
  patients: 'https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=400&q=60',
  completion: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&q=60',
  analytics: 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&q=60',
  marketing: 'https://images.unsplash.com/photo-1533750349088-cd871a92f312?w=400&q=60',
  dental: 'https://images.unsplash.com/photo-1606811971618-4486d14f3f99?w=400&q=60',
  clinic: 'https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=400&q=60',
  tech: 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=400&q=60',
  team: 'https://images.unsplash.com/photo-1521791136064-7986c2920216?w=400&q=60',
  calendar: 'https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=400&q=60',
  chat: 'https://images.unsplash.com/photo-1577563908411-5077b6dc7624?w=400&q=60',
  leads: 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=400&q=60',
  tokens: 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=400&q=60',
  profile: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&q=60',
};
