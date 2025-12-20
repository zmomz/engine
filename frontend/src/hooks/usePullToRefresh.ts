import { useEffect, useRef, useState, useCallback } from 'react';

interface PullToRefreshOptions {
  onRefresh: () => Promise<void> | void;
  threshold?: number;
  disabled?: boolean;
}

interface PullToRefreshState {
  isPulling: boolean;
  pullDistance: number;
  isRefreshing: boolean;
}

export const usePullToRefresh = (options: PullToRefreshOptions): PullToRefreshState => {
  const { onRefresh, threshold = 80, disabled = false } = options;
  const [state, setState] = useState<PullToRefreshState>({
    isPulling: false,
    pullDistance: 0,
    isRefreshing: false,
  });

  const startY = useRef<number>(0);
  const currentY = useRef<number>(0);

  const handleTouchStart = useCallback((e: TouchEvent) => {
    if (disabled || state.isRefreshing) return;

    // Only trigger if scrolled to top
    if (window.scrollY > 0) return;

    startY.current = e.touches[0].clientY;
    setState(prev => ({ ...prev, isPulling: true }));
  }, [disabled, state.isRefreshing]);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!state.isPulling || disabled || state.isRefreshing) return;

    currentY.current = e.touches[0].clientY;
    const distance = Math.max(0, currentY.current - startY.current);

    // Apply resistance to make it feel natural
    const resistedDistance = Math.min(distance * 0.5, threshold * 1.5);

    setState(prev => ({ ...prev, pullDistance: resistedDistance }));
  }, [state.isPulling, disabled, state.isRefreshing, threshold]);

  const handleTouchEnd = useCallback(async () => {
    if (!state.isPulling || disabled) return;

    if (state.pullDistance >= threshold) {
      setState(prev => ({ ...prev, isRefreshing: true, pullDistance: threshold }));

      try {
        await onRefresh();
      } finally {
        setState({ isPulling: false, pullDistance: 0, isRefreshing: false });
      }
    } else {
      setState({ isPulling: false, pullDistance: 0, isRefreshing: false });
    }
  }, [state.isPulling, state.pullDistance, threshold, onRefresh, disabled]);

  useEffect(() => {
    if (disabled) return;

    window.addEventListener('touchstart', handleTouchStart, { passive: true });
    window.addEventListener('touchmove', handleTouchMove, { passive: true });
    window.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      window.removeEventListener('touchstart', handleTouchStart);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd, disabled]);

  return state;
};

export default usePullToRefresh;
