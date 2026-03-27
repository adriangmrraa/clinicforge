import React, { useState, useEffect } from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  image?: string;
  className?: string;
  hoverScale?: boolean;
  onClick?: () => void;
}

/**
 * Reusable glass card with optional background image that fades in on hover/touch.
 * Images are blurred and very subtle. Ken Burns slow animation on hover.
 */
const GlassCard: React.FC<GlassCardProps> = ({
  children,
  image,
  className = '',
  hoverScale = true,
  onClick,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const [imgLoaded, setImgLoaded] = useState(false);

  // Preload image
  useEffect(() => {
    if (image) {
      const img = new Image();
      img.src = image;
      img.onload = () => setImgLoaded(true);
    }
  }, [image]);

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-white/[0.06] transition-all duration-300 ease-out group ${onClick ? 'cursor-pointer' : ''} ${className}`}
      style={{
        transform: isHovered && hoverScale ? 'scale(1.015)' : 'scale(1)',
        transition: 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.4s ease',
        boxShadow: isHovered ? '0 8px 40px rgba(0,0,0,0.25)' : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onTouchStart={() => setIsHovered(true)}
      onTouchEnd={() => setTimeout(() => setIsHovered(false), 500)}
      onClick={onClick}
    >
      {/* Background image — blurred, very subtle, with Ken Burns animation */}
      {image && imgLoaded && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: `url(${image})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            filter: 'blur(2px)',
            opacity: isHovered ? 0.08 : 0.03,
            transition: 'opacity 0.6s ease-out, transform 8s ease-out',
            transform: isHovered ? 'scale(1.1)' : 'scale(1.02)',
          }}
        />
      )}

      {/* Dark overlay to keep content readable */}
      <div
        className="absolute inset-0 pointer-events-none transition-all duration-500"
        style={{
          background: isHovered
            ? 'linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(59,130,246,0.03) 50%, transparent 100%)'
            : 'linear-gradient(135deg, rgba(255,255,255,0.02) 0%, transparent 100%)',
        }}
      />

      {/* Hover glow — very subtle bottom edge */}
      <div
        className="absolute inset-x-0 bottom-0 h-px pointer-events-none transition-opacity duration-500"
        style={{
          background: 'linear-gradient(90deg, transparent, rgba(59,130,246,0.3), transparent)',
          opacity: isHovered ? 1 : 0,
        }}
      />

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
