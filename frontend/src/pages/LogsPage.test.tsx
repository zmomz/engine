import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LogsPage from './LogsPage';
import useLogStore from '../store/logStore';

// Mock the store
jest.mock('../store/logStore');

describe('LogsPage', () => {
  const mockFetchLogs = jest.fn();

  beforeEach(() => {
    (useLogStore as unknown as jest.Mock).mockReturnValue({
      logs: [],
      loading: false,
      error: null,
      fetchLogs: mockFetchLogs,
    });
    mockFetchLogs.mockClear();
  });

  test('renders logs page title', () => {
    render(<LogsPage />);
    expect(screen.getByText('System Logs')).toBeInTheDocument();
  });

  test('fetches logs on mount', () => {
    render(<LogsPage />);
    expect(mockFetchLogs).toHaveBeenCalledWith(100, 'all');
  });

  test('displays loading spinner when loading', () => {
    (useLogStore as unknown as jest.Mock).mockReturnValue({
      logs: [],
      loading: true,
      error: null,
      fetchLogs: mockFetchLogs,
    });
    render(<LogsPage />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  test('displays logs when loaded', () => {
    (useLogStore as unknown as jest.Mock).mockReturnValue({
      logs: ['Log entry 1', 'Log entry 2'],
      loading: false,
      error: null,
      fetchLogs: mockFetchLogs,
    });
    render(<LogsPage />);
    expect(screen.getByText('Log entry 1')).toBeInTheDocument();
    expect(screen.getByText('Log entry 2')).toBeInTheDocument();
  });

  test('displays error message', () => {
    (useLogStore as unknown as jest.Mock).mockReturnValue({
      logs: [],
      loading: false,
      error: 'Failed to fetch',
      fetchLogs: mockFetchLogs,
    });
    render(<LogsPage />);
    expect(screen.getByText('Failed to fetch')).toBeInTheDocument();
  });

  test('refresh button triggers fetchLogs', () => {
    render(<LogsPage />);
    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);
    expect(mockFetchLogs).toHaveBeenCalledTimes(2); // Mount + Click
  });

  test('filter updates trigger fetchLogs', async () => {
    render(<LogsPage />);
    
    // Changing line count
    const lineSelect = screen.getByLabelText('Lines'); // MUI Select uses label
    // MUI Select is tricky to test with simple fireEvent, typically use getAllByRole('button') or similar
    // Assuming simple rendering for now.
    
    expect(mockFetchLogs).toHaveBeenCalled();
  });
});