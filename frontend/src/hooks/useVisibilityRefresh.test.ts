import { renderHook, act } from '@testing-library/react';
import { useVisibilityRefresh } from './useVisibilityRefresh';

describe('useVisibilityRefresh', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const simulateVisibilityChange = (hidden: boolean) => {
    Object.defineProperty(document, 'hidden', {
      value: hidden,
      writable: true,
      configurable: true,
    });

    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
  };

  test('does not call onVisible immediately', () => {
    const onVisible = jest.fn();
    renderHook(() => useVisibilityRefresh(onVisible));

    expect(onVisible).not.toHaveBeenCalled();
  });

  test('calls onVisible when page becomes visible after being hidden for more than 2 seconds', () => {
    const onVisible = jest.fn();
    renderHook(() => useVisibilityRefresh(onVisible));

    // Simulate page being hidden
    simulateVisibilityChange(true);

    // Advance time by more than 2 seconds
    act(() => {
      jest.advanceTimersByTime(3000);
    });

    // Simulate page becoming visible again
    simulateVisibilityChange(false);

    expect(onVisible).toHaveBeenCalledTimes(1);
  });

  test('does not call onVisible when page was hidden for less than 2 seconds', () => {
    const onVisible = jest.fn();
    renderHook(() => useVisibilityRefresh(onVisible));

    // Simulate page being hidden
    simulateVisibilityChange(true);

    // Advance time by less than 2 seconds
    act(() => {
      jest.advanceTimersByTime(1000);
    });

    // Simulate page becoming visible again
    simulateVisibilityChange(false);

    expect(onVisible).not.toHaveBeenCalled();
  });

  test('does not set up listener when disabled', () => {
    const addEventListenerSpy = jest.spyOn(document, 'addEventListener');
    const onVisible = jest.fn();

    renderHook(() => useVisibilityRefresh(onVisible, false));

    // Should not add event listener when disabled
    expect(addEventListenerSpy).not.toHaveBeenCalledWith('visibilitychange', expect.any(Function));

    addEventListenerSpy.mockRestore();
  });

  test('cleans up event listener on unmount', () => {
    const removeEventListenerSpy = jest.spyOn(document, 'removeEventListener');
    const onVisible = jest.fn();

    const { unmount } = renderHook(() => useVisibilityRefresh(onVisible));
    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));

    removeEventListenerSpy.mockRestore();
  });

  test('handles multiple visibility changes correctly', () => {
    const onVisible = jest.fn();
    renderHook(() => useVisibilityRefresh(onVisible));

    // First hide/show cycle (< 2 seconds)
    simulateVisibilityChange(true);
    act(() => { jest.advanceTimersByTime(1000); });
    simulateVisibilityChange(false);
    expect(onVisible).not.toHaveBeenCalled();

    // Second hide/show cycle (> 2 seconds)
    simulateVisibilityChange(true);
    act(() => { jest.advanceTimersByTime(3000); });
    simulateVisibilityChange(false);
    expect(onVisible).toHaveBeenCalledTimes(1);

    // Third hide/show cycle (> 2 seconds)
    simulateVisibilityChange(true);
    act(() => { jest.advanceTimersByTime(5000); });
    simulateVisibilityChange(false);
    expect(onVisible).toHaveBeenCalledTimes(2);
  });

  test('handles visibility change when lastHiddenTime is null', () => {
    const onVisible = jest.fn();
    renderHook(() => useVisibilityRefresh(onVisible));

    // Simulate page becoming visible without prior hidden state
    simulateVisibilityChange(false);

    // Should not call onVisible since page was never hidden
    expect(onVisible).not.toHaveBeenCalled();
  });
});
