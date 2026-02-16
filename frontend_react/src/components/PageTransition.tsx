import React, { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

interface PageTransitionProps {
  children: React.ReactNode;
}

export const PageTransition: React.FC<PageTransitionProps> = ({ children }) => {
  const location = useLocation();
  const previousPath = useRef(location.pathname);

  useEffect(() => {
    // Trigger page transition animation
    const content = document.getElementById('page-content');
    if (content) {
      content.classList.add('page-exit');
      setTimeout(() => {
        content.classList.remove('page-exit');
        content.classList.add('page-enter');
      }, 50);
    }
  }, [location.pathname]);

  return (
    <div 
      id="page-content"
      className="page-enter"
    >
      {children}
    </div>
  );
};

// Hook for staggered list animations
export const useStaggeredAnimation = (itemCount: number, baseDelay = 50) => {
  return Array.from({ length: itemCount }).map((_, i) => ({
    animationDelay: `${i * baseDelay}ms`,
  }));
};

// Animated list item
export const AnimatedListItem: React.FC<{
  children: React.ReactNode;
  index: number;
  className?: string;
}> = ({ children, index, className = '' }) => (
  <div
    className={`animate-slide-up ${className}`}
    style={{ animationDelay: `${index * 75}ms` }}
  >
    {children}
  </div>
);

// Fade in animation component
export const FadeIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  className?: string;
}> = ({ children, delay = 0, className = '' }) => (
  <div
    className={`animate-fade-in ${className}`}
    style={{ animationDelay: `${delay}ms` }}
  >
    {children}
  </div>
);

// Scale in animation component
export const ScaleIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  className?: string;
}> = ({ children, delay = 0, className = '' }) => (
  <div
    className={`animate-scale-in ${className}`}
    style={{ animationDelay: `${delay}ms` }}
  >
    {children}
  </div>
);

// Slide in from side
export const SlideIn: React.FC<{
  children: React.ReactNode;
  from?: 'left' | 'right';
  delay?: number;
  className?: string;
}> = ({ children, from = 'left', delay = 0, className = '' }) => (
  <div
    className={`animate-slide-in-${from} ${className}`}
    style={{ animationDelay: `${delay}ms` }}
  >
    {children}
  </div>
);

export default PageTransition;
