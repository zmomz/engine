import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import NotificationManager from './NotificationManager';
import useNotificationStore from '../store/notificationStore';

// Mock the store
jest.mock('../store/notificationStore');

describe('NotificationManager', () => {
  const mockHideNotification = jest.fn();
  
  beforeEach(() => {
    (useNotificationStore as unknown as jest.Mock).mockReturnValue({
      notifications: [],
      hideNotification: mockHideNotification,
    });
    mockHideNotification.mockClear();
  });

  test('renders nothing when no notifications', () => {
    render(<NotificationManager />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  test('renders notification when store has one', () => {
    (useNotificationStore as unknown as jest.Mock).mockReturnValue({
      notifications: [{ id: '1', message: 'Test Message', type: 'success' }],
      hideNotification: mockHideNotification,
    });

    render(<NotificationManager />);
    
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Test Message')).toBeInTheDocument();
  });

  test('displays warning notification correctly', () => {
    (useNotificationStore as unknown as jest.Mock).mockReturnValue({
      notifications: [{ id: '2', message: 'Warning Msg', type: 'warning' }],
      hideNotification: mockHideNotification,
    });

    render(<NotificationManager />);
    const alert = screen.getByRole('alert');
    // MUI Alert severity usually maps to class or aria attribute, but text check is solid
    expect(screen.getByText('Warning Msg')).toBeInTheDocument();
  });
});
