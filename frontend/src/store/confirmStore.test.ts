import { act, renderHook } from '@testing-library/react';
import useConfirmStore from './confirmStore';

describe('confirmStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    const { result } = renderHook(() => useConfirmStore());
    act(() => {
      result.current.closeConfirm(false);
    });
  });

  test('initializes with default state', () => {
    const { result } = renderHook(() => useConfirmStore());

    expect(result.current.isOpen).toBe(false);
    expect(result.current.options).toEqual({ message: '' });
    expect(result.current.resolve).toBeNull();
  });

  test('requestConfirm opens dialog and sets options', async () => {
    const { result } = renderHook(() => useConfirmStore());

    const options = {
      title: 'Confirm Action',
      message: 'Are you sure?',
      confirmText: 'Yes',
      cancelText: 'No',
    };

    let promise: Promise<boolean>;
    act(() => {
      promise = result.current.requestConfirm(options);
    });

    expect(result.current.isOpen).toBe(true);
    expect(result.current.options).toEqual(options);
    expect(result.current.resolve).not.toBeNull();
  });

  test('closeConfirm resolves promise with true when confirmed', async () => {
    const { result } = renderHook(() => useConfirmStore());

    let resolvedValue: boolean | undefined;

    act(() => {
      result.current.requestConfirm({ message: 'Test' }).then((value) => {
        resolvedValue = value;
      });
    });

    act(() => {
      result.current.closeConfirm(true);
    });

    // Wait for promise to resolve
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(resolvedValue).toBe(true);
    expect(result.current.isOpen).toBe(false);
    expect(result.current.resolve).toBeNull();
  });

  test('closeConfirm resolves promise with false when cancelled', async () => {
    const { result } = renderHook(() => useConfirmStore());

    let resolvedValue: boolean | undefined;

    act(() => {
      result.current.requestConfirm({ message: 'Test' }).then((value) => {
        resolvedValue = value;
      });
    });

    act(() => {
      result.current.closeConfirm(false);
    });

    // Wait for promise to resolve
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(resolvedValue).toBe(false);
    expect(result.current.isOpen).toBe(false);
  });

  test('handles multiple confirmation requests sequentially', async () => {
    const { result } = renderHook(() => useConfirmStore());

    // First request
    let firstResult: boolean | undefined;
    act(() => {
      result.current.requestConfirm({ message: 'First' }).then((value) => {
        firstResult = value;
      });
    });

    act(() => {
      result.current.closeConfirm(true);
    });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(firstResult).toBe(true);

    // Second request
    let secondResult: boolean | undefined;
    act(() => {
      result.current.requestConfirm({ message: 'Second' }).then((value) => {
        secondResult = value;
      });
    });

    act(() => {
      result.current.closeConfirm(false);
    });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(secondResult).toBe(false);
  });

  test('requestConfirm with minimal options', async () => {
    const { result } = renderHook(() => useConfirmStore());

    act(() => {
      result.current.requestConfirm({ message: 'Simple message' });
    });

    expect(result.current.options.message).toBe('Simple message');
    expect(result.current.options.title).toBeUndefined();
    expect(result.current.options.confirmText).toBeUndefined();
    expect(result.current.options.cancelText).toBeUndefined();
  });

  test('closeConfirm handles case when resolve is null', () => {
    const { result } = renderHook(() => useConfirmStore());

    // This should not throw
    act(() => {
      result.current.closeConfirm(true);
    });

    expect(result.current.isOpen).toBe(false);
  });
});
