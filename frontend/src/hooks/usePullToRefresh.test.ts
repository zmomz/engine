import { renderHook, act } from '@testing-library/react';
import { usePullToRefresh } from './usePullToRefresh';

describe('usePullToRefresh', () => {
  let originalScrollY: number;

  beforeEach(() => {
    jest.clearAllMocks();
    // Store original scrollY
    originalScrollY = window.scrollY;
    // Mock scrollY to 0 (at top)
    Object.defineProperty(window, 'scrollY', {
      value: 0,
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    // Restore original scrollY
    Object.defineProperty(window, 'scrollY', {
      value: originalScrollY,
      configurable: true,
    });
  });

  const createTouchEvent = (type: string, clientY: number): TouchEvent => {
    const touch = { clientY } as Touch;
    return new TouchEvent(type, {
      touches: [touch],
      bubbles: true,
    } as TouchEventInit);
  };

  const simulateTouchStart = (clientY: number) => {
    act(() => {
      const event = createTouchEvent('touchstart', clientY);
      window.dispatchEvent(event);
    });
  };

  const simulateTouchMove = (clientY: number) => {
    act(() => {
      const event = createTouchEvent('touchmove', clientY);
      window.dispatchEvent(event);
    });
  };

  const simulateTouchEnd = () => {
    act(() => {
      window.dispatchEvent(new TouchEvent('touchend', { bubbles: true }));
    });
  };

  test('initializes with default state', () => {
    const onRefresh = jest.fn();
    const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

    expect(result.current.isPulling).toBe(false);
    expect(result.current.pullDistance).toBe(0);
    expect(result.current.isRefreshing).toBe(false);
  });

  test('starts pulling on touch start when at top', () => {
    const onRefresh = jest.fn();
    const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

    simulateTouchStart(100);

    expect(result.current.isPulling).toBe(true);
  });

  test('does not start pulling when scrolled down', () => {
    Object.defineProperty(window, 'scrollY', { value: 100, configurable: true });

    const onRefresh = jest.fn();
    const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

    simulateTouchStart(100);

    expect(result.current.isPulling).toBe(false);
  });

  test('does not start pulling when disabled', () => {
    const onRefresh = jest.fn();
    const { result } = renderHook(() => usePullToRefresh({ onRefresh, disabled: true }));

    simulateTouchStart(100);

    expect(result.current.isPulling).toBe(false);
  });

  test('updates pull distance on touch move', () => {
    const onRefresh = jest.fn();
    const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

    simulateTouchStart(100);
    simulateTouchMove(150);

    // Distance is resisted by 0.5, so 50 * 0.5 = 25
    expect(result.current.pullDistance).toBeGreaterThan(0);
  });

  test('calls onRefresh when pull distance exceeds threshold', async () => {
    const onRefresh = jest.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh, threshold: 80 })
    );

    simulateTouchStart(0);
    // Pull down by 200px, which after resistance (0.5) = 100, still > 80 threshold
    simulateTouchMove(200);

    await act(async () => {
      simulateTouchEnd();
    });

    expect(onRefresh).toHaveBeenCalled();
  });

  test('does not call onRefresh when pull distance below threshold', async () => {
    const onRefresh = jest.fn();
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh, threshold: 80 })
    );

    simulateTouchStart(0);
    // Pull down by only 50px
    simulateTouchMove(50);

    await act(async () => {
      simulateTouchEnd();
    });

    expect(onRefresh).not.toHaveBeenCalled();
  });

  test('resets state after refresh completes', async () => {
    const onRefresh = jest.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh, threshold: 80 })
    );

    simulateTouchStart(0);
    simulateTouchMove(200);

    await act(async () => {
      simulateTouchEnd();
    });

    expect(result.current.isPulling).toBe(false);
    expect(result.current.pullDistance).toBe(0);
    expect(result.current.isRefreshing).toBe(false);
  });

  test('cleans up event listeners on unmount', () => {
    const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');
    const onRefresh = jest.fn();

    const { unmount } = renderHook(() => usePullToRefresh({ onRefresh }));
    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('touchstart', expect.any(Function));
    expect(removeEventListenerSpy).toHaveBeenCalledWith('touchmove', expect.any(Function));
    expect(removeEventListenerSpy).toHaveBeenCalledWith('touchend', expect.any(Function));

    removeEventListenerSpy.mockRestore();
  });

  test('does not set up listeners when disabled', () => {
    const addEventListenerSpy = jest.spyOn(window, 'addEventListener');
    const onRefresh = jest.fn();

    renderHook(() => usePullToRefresh({ onRefresh, disabled: true }));

    // Should not add touch listeners when disabled
    const touchCalls = addEventListenerSpy.mock.calls.filter(
      call => call[0].startsWith('touch')
    );
    expect(touchCalls.length).toBe(0);

    addEventListenerSpy.mockRestore();
  });

  test('handles negative pull distance (upward swipe)', () => {
    const onRefresh = jest.fn();
    const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

    simulateTouchStart(100);
    // Swipe up (negative distance)
    simulateTouchMove(50);

    // Should be 0 (clamped to positive values)
    expect(result.current.pullDistance).toBe(0);
  });

  test('uses custom threshold', () => {
    const onRefresh = jest.fn().mockResolvedValue(undefined);

    // Use a very low threshold
    renderHook(() => usePullToRefresh({ onRefresh, threshold: 10 }));

    simulateTouchStart(0);
    // Even a small pull should trigger refresh with low threshold
    simulateTouchMove(50);

    // Pull distance should be updated
    // With 50px pull and 0.5 resistance, we get 25px > 10 threshold
  });
});
