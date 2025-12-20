import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

interface ResponsiveTableWrapperProps {
  children: React.ReactNode;
  showIndicators?: boolean;
}

const ResponsiveTableWrapper: React.FC<ResponsiveTableWrapperProps> = ({
  children,
  showIndicators = true,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const containerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const { scrollLeft, scrollWidth, clientWidth } = container;
    setCanScrollLeft(scrollLeft > 5);
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 5);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Initial check
    checkScroll();

    // Check on scroll
    container.addEventListener('scroll', checkScroll);

    // Check on resize
    const resizeObserver = new ResizeObserver(checkScroll);
    resizeObserver.observe(container);

    return () => {
      container.removeEventListener('scroll', checkScroll);
      resizeObserver.disconnect();
    };
  }, [checkScroll]);

  // Also check when children change (e.g., data loads)
  useEffect(() => {
    // Small delay to let content render
    const timeout = setTimeout(checkScroll, 100);
    return () => clearTimeout(timeout);
  }, [children, checkScroll]);

  const handleScrollLeft = () => {
    const container = containerRef.current;
    if (!container) return;
    container.scrollBy({ left: -200, behavior: 'smooth' });
  };

  const handleScrollRight = () => {
    const container = containerRef.current;
    if (!container) return;
    container.scrollBy({ left: 200, behavior: 'smooth' });
  };

  if (!isMobile) {
    // On desktop, just render children without wrapper
    return <>{children}</>;
  }

  return (
    <Box sx={{ position: 'relative', height: '100%', overflow: 'hidden' }}>
      {/* Left scroll indicator */}
      {showIndicators && canScrollLeft && (
        <Box
          onClick={handleScrollLeft}
          sx={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: `linear-gradient(to right, ${theme.palette.background.paper} 0%, transparent 100%)`,
            zIndex: 10,
            cursor: 'pointer',
            '&:hover': {
              '& .scroll-icon': {
                transform: 'translateX(-2px)',
              },
            },
          }}
        >
          <ChevronLeftIcon
            className="scroll-icon"
            sx={{
              color: 'primary.main',
              fontSize: 24,
              transition: 'transform 0.2s',
              animation: 'pulse-left 1.5s infinite',
              '@keyframes pulse-left': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.5 },
              },
            }}
          />
        </Box>
      )}

      {/* Right scroll indicator */}
      {showIndicators && canScrollRight && (
        <Box
          onClick={handleScrollRight}
          sx={{
            position: 'absolute',
            right: 0,
            top: 0,
            bottom: 0,
            width: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: `linear-gradient(to left, ${theme.palette.background.paper} 0%, transparent 100%)`,
            zIndex: 10,
            cursor: 'pointer',
            '&:hover': {
              '& .scroll-icon': {
                transform: 'translateX(2px)',
              },
            },
          }}
        >
          <ChevronRightIcon
            className="scroll-icon"
            sx={{
              color: 'primary.main',
              fontSize: 24,
              transition: 'transform 0.2s',
              animation: 'pulse-right 1.5s infinite',
              '@keyframes pulse-right': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.5 },
              },
            }}
          />
        </Box>
      )}

      {/* Scrollable container */}
      <Box
        ref={containerRef}
        sx={{
          height: '100%',
          overflowX: 'auto',
          overflowY: 'hidden',
          WebkitOverflowScrolling: 'touch',
          // Hide scrollbar on mobile for cleaner look (still scrollable)
          scrollbarWidth: 'none',
          '&::-webkit-scrollbar': {
            display: 'none',
          },
        }}
      >
        {children}
      </Box>

      {/* Bottom hint text */}
      {showIndicators && (canScrollLeft || canScrollRight) && (
        <Box
          sx={{
            position: 'absolute',
            bottom: 8,
            left: '50%',
            transform: 'translateX(-50%)',
            bgcolor: 'rgba(0, 0, 0, 0.6)',
            color: 'white',
            px: 1.5,
            py: 0.5,
            borderRadius: 1,
            fontSize: '0.65rem',
            pointerEvents: 'none',
            opacity: 0.7,
            zIndex: 5,
          }}
        >
          Swipe to see more →
        </Box>
      )}
    </Box>
  );
};

export default ResponsiveTableWrapper;
