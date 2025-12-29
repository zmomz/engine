import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter, useNavigate, useLocation } from 'react-router-dom';
import { useKeyboardShortcuts } from './useKeyboardShortcuts';

// Mock react-router-dom hooks
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: jest.fn(),
  useLocation: jest.fn(),
}));

describe('useKeyboardShortcuts', () => {
  const mockNavigate = jest.fn();
  const mockLocation = { pathname: '/dashboard' };

  beforeEach(() => {
    jest.clearAllMocks();
    (useNavigate as jest.Mock).mockReturnValue(mockNavigate);
    (useLocation as jest.Mock).mockReturnValue(mockLocation);
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <MemoryRouter>{children}</MemoryRouter>
  );

  const fireKeyboardEvent = (key: string, options: Partial<KeyboardEventInit> = {}) => {
    const event = new KeyboardEvent('keydown', {
      key,
      bubbles: true,
      ...options,
    });
    act(() => {
      window.dispatchEvent(event);
    });
  };

  test('navigates to overview on Alt+1', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('1', { altKey: true });

    expect(mockNavigate).toHaveBeenCalledWith('/overview');
  });

  test('navigates to dashboard on Alt+2', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('2', { altKey: true });

    expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
  });

  test('navigates to positions on Alt+3', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('3', { altKey: true });

    expect(mockNavigate).toHaveBeenCalledWith('/positions');
  });

  test('navigates to queue on Alt+4', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('4', { altKey: true });

    expect(mockNavigate).toHaveBeenCalledWith('/queue');
  });

  test('navigates to risk on Alt+5', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('5', { altKey: true });

    expect(mockNavigate).toHaveBeenCalledWith('/risk');
  });

  test('navigates to analytics on Alt+6', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('6', { altKey: true });

    expect(mockNavigate).toHaveBeenCalledWith('/analytics');
  });

  test('navigates to settings on Alt+7', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('7', { altKey: true });

    expect(mockNavigate).toHaveBeenCalledWith('/settings');
  });

  test('calls onRefresh on Ctrl+R', () => {
    const onRefresh = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onRefresh }), { wrapper });

    fireKeyboardEvent('r', { ctrlKey: true });

    expect(onRefresh).toHaveBeenCalled();
  });

  test('calls onForceStart on F key when on risk page', () => {
    (useLocation as jest.Mock).mockReturnValue({ pathname: '/risk' });
    const onForceStart = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onForceStart }), { wrapper });

    fireKeyboardEvent('f');

    expect(onForceStart).toHaveBeenCalled();
  });

  test('calls onForceStop on S key when on risk page', () => {
    (useLocation as jest.Mock).mockReturnValue({ pathname: '/risk' });
    const onForceStop = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onForceStop }), { wrapper });

    fireKeyboardEvent('s');

    expect(onForceStop).toHaveBeenCalled();
  });

  test('calls onRunRiskEvaluation on E key when on risk page', () => {
    (useLocation as jest.Mock).mockReturnValue({ pathname: '/risk' });
    const onRunRiskEvaluation = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onRunRiskEvaluation }), { wrapper });

    fireKeyboardEvent('e');

    expect(onRunRiskEvaluation).toHaveBeenCalled();
  });

  test('also triggers shortcuts on overview page for F/S/E keys', () => {
    (useLocation as jest.Mock).mockReturnValue({ pathname: '/overview' });
    const onForceStart = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onForceStart }), { wrapper });

    fireKeyboardEvent('f');

    expect(onForceStart).toHaveBeenCalled();
  });

  test('does not call shortcut handlers when Alt key is combined with Ctrl', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('1', { altKey: true, ctrlKey: true });

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('does not navigate on non-navigation keys with Alt', () => {
    renderHook(() => useKeyboardShortcuts(), { wrapper });

    fireKeyboardEvent('8', { altKey: true });
    fireKeyboardEvent('9', { altKey: true });

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('does not call F/S/E shortcuts on non-risk pages', () => {
    (useLocation as jest.Mock).mockReturnValue({ pathname: '/dashboard' });
    const onForceStart = jest.fn();
    const onForceStop = jest.fn();
    const onRunRiskEvaluation = jest.fn();

    renderHook(() => useKeyboardShortcuts({ onForceStart, onForceStop, onRunRiskEvaluation }), { wrapper });

    fireKeyboardEvent('f');
    fireKeyboardEvent('s');
    fireKeyboardEvent('e');

    expect(onForceStart).not.toHaveBeenCalled();
    expect(onForceStop).not.toHaveBeenCalled();
    expect(onRunRiskEvaluation).not.toHaveBeenCalled();
  });

  test('cleans up event listener on unmount', () => {
    const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');

    const { unmount } = renderHook(() => useKeyboardShortcuts(), { wrapper });
    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

    removeEventListenerSpy.mockRestore();
  });
});
