import { useEffect, useRef } from 'react';

/**
 * Hook that triggers a callback when the page becomes visible again.
 * Useful for refreshing data when user returns to the tab.
 *
 * @param onVisible - Callback to execute when page becomes visible
 * @param enabled - Whether the hook is active (default: true)
 */
export function useVisibilityRefresh(
  onVisible: () => void,
  enabled: boolean = true
) {
  const lastHiddenTime = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Page is being hidden, record the time
        lastHiddenTime.current = Date.now();
      } else {
        // Page is becoming visible
        // Only refresh if page was hidden for more than 2 seconds
        // This avoids unnecessary refreshes from brief tab switches
        const hiddenDuration = lastHiddenTime.current
          ? Date.now() - lastHiddenTime.current
          : 0;

        if (hiddenDuration > 2000) {
          onVisible();
        }
        lastHiddenTime.current = null;
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [onVisible, enabled]);
}

export default useVisibilityRefresh;
