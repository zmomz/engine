import { act, renderHook } from '@testing-library/react';
import useNotificationStore from './notificationStore';

describe('notificationStore', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    // Reset store state before each test
    const { result } = renderHook(() => useNotificationStore());
    act(() => {
      result.current.notifications.forEach((n) => {
        result.current.hideNotification(n.id);
      });
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('initializes with empty notifications', () => {
    const { result } = renderHook(() => useNotificationStore());

    expect(result.current.notifications).toEqual([]);
  });

  test('showNotification adds a notification', () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.showNotification('Test message', 'success');
    });

    expect(result.current.notifications).toHaveLength(1);
    expect(result.current.notifications[0].message).toBe('Test message');
    expect(result.current.notifications[0].type).toBe('success');
    expect(result.current.notifications[0].id).toBeTruthy();
  });

  test('showNotification adds multiple notifications', () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.showNotification('Message 1', 'success');
      result.current.showNotification('Message 2', 'error');
      result.current.showNotification('Message 3', 'warning');
    });

    expect(result.current.notifications).toHaveLength(3);
    expect(result.current.notifications[0].message).toBe('Message 1');
    expect(result.current.notifications[1].message).toBe('Message 2');
    expect(result.current.notifications[2].message).toBe('Message 3');
  });

  test('showNotification supports all notification types', () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.showNotification('Success', 'success');
      result.current.showNotification('Error', 'error');
      result.current.showNotification('Info', 'info');
      result.current.showNotification('Warning', 'warning');
    });

    expect(result.current.notifications[0].type).toBe('success');
    expect(result.current.notifications[1].type).toBe('error');
    expect(result.current.notifications[2].type).toBe('info');
    expect(result.current.notifications[3].type).toBe('warning');
  });

  test('hideNotification removes a specific notification', () => {
    // Pause timers to prevent auto-dismiss from interfering
    jest.useFakeTimers();

    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.showNotification('Message 1', 'success');
    });

    // Need a small delay between notifications due to Date.now() being same
    act(() => {
      jest.advanceTimersByTime(1);
      result.current.showNotification('Message 2', 'error');
    });

    expect(result.current.notifications).toHaveLength(2);

    const idToRemove = result.current.notifications[0].id;

    act(() => {
      result.current.hideNotification(idToRemove);
    });

    expect(result.current.notifications).toHaveLength(1);
    expect(result.current.notifications[0].message).toBe('Message 2');
  });

  test('notifications auto-dismiss after 6 seconds', () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.showNotification('Auto-dismiss test', 'info');
    });

    expect(result.current.notifications).toHaveLength(1);

    // Advance timer by 6 seconds
    act(() => {
      jest.advanceTimersByTime(6000);
    });

    expect(result.current.notifications).toHaveLength(0);
  });

  test('hideNotification with non-existent id does not throw', () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.showNotification('Message', 'success');
    });

    // Try to hide a non-existent notification
    act(() => {
      result.current.hideNotification('non-existent-id');
    });

    // Original notification should still exist
    expect(result.current.notifications).toHaveLength(1);
  });

  test('each notification gets a unique id', () => {
    const { result } = renderHook(() => useNotificationStore());

    // Mock Date.now to return different values
    const originalDateNow = Date.now;
    let counter = 1000;
    Date.now = jest.fn(() => counter++);

    act(() => {
      result.current.showNotification('Message 1', 'success');
      result.current.showNotification('Message 2', 'success');
    });

    expect(result.current.notifications[0].id).not.toBe(result.current.notifications[1].id);

    Date.now = originalDateNow;
  });
});
