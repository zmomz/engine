import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LogsPage from './LogsPage';
import useLogStore from '../store/logStore';

// Mock the store
jest.mock('../store/logStore');

describe('LogsPage', () => {
  const mockFetchLogs = jest.fn();

  beforeEach(() => {
    jest.useFakeTimers();
    (useLogStore as unknown as jest.Mock).mockReturnValue({
      logs: [],
      loading: false,
      error: null,
      fetchLogs: mockFetchLogs,
    });
    mockFetchLogs.mockClear();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    test('renders logs page title', () => {
      render(<LogsPage />);
      expect(screen.getByText('System Logs')).toBeInTheDocument();
    });

    test('renders filter controls', () => {
      render(<LogsPage />);
      expect(screen.getByLabelText('Level')).toBeInTheDocument();
      expect(screen.getByLabelText('Lines')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Search logs...')).toBeInTheDocument();
    });

    test('renders action buttons', () => {
      render(<LogsPage />);
      expect(screen.getByText('Refresh')).toBeInTheDocument();
      expect(screen.getByText('Export Logs')).toBeInTheDocument();
    });

    test('displays loading spinner when loading with no logs', () => {
      (useLogStore as unknown as jest.Mock).mockReturnValue({
        logs: [],
        loading: true,
        error: null,
        fetchLogs: mockFetchLogs,
      });
      render(<LogsPage />);
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    test('does not show spinner when loading with existing logs', () => {
      (useLogStore as unknown as jest.Mock).mockReturnValue({
        logs: ['Existing log'],
        loading: true,
        error: null,
        fetchLogs: mockFetchLogs,
      });
      render(<LogsPage />);
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      expect(screen.getByText('Existing log')).toBeInTheDocument();
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

    test('displays no logs message when empty', () => {
      (useLogStore as unknown as jest.Mock).mockReturnValue({
        logs: [],
        loading: false,
        error: null,
        fetchLogs: mockFetchLogs,
      });
      render(<LogsPage />);
      expect(screen.getByText('No logs found.')).toBeInTheDocument();
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
  });

  describe('Data Fetching', () => {
    test('fetches logs on mount', () => {
      render(<LogsPage />);
      expect(mockFetchLogs).toHaveBeenCalledWith(100, 'all');
    });

    test('auto-refreshes every 5 seconds', () => {
      render(<LogsPage />);
      expect(mockFetchLogs).toHaveBeenCalledTimes(1);

      // Advance 5 seconds
      act(() => {
        jest.advanceTimersByTime(5000);
      });
      expect(mockFetchLogs).toHaveBeenCalledTimes(2);

      // Advance another 5 seconds
      act(() => {
        jest.advanceTimersByTime(5000);
      });
      expect(mockFetchLogs).toHaveBeenCalledTimes(3);
    });

    test('clears interval on unmount', () => {
      const { unmount } = render(<LogsPage />);
      expect(mockFetchLogs).toHaveBeenCalledTimes(1);

      unmount();

      // Advance time after unmount
      act(() => {
        jest.advanceTimersByTime(10000);
      });

      // Should still be 1 (no additional calls)
      expect(mockFetchLogs).toHaveBeenCalledTimes(1);
    });
  });

  describe('User Interactions', () => {
    test('refresh button triggers fetchLogs', () => {
      render(<LogsPage />);
      const refreshButton = screen.getByText('Refresh');
      fireEvent.click(refreshButton);
      expect(mockFetchLogs).toHaveBeenCalledTimes(2); // Mount + Click
    });

    test('changing log level triggers fetchLogs', async () => {
      render(<LogsPage />);
      mockFetchLogs.mockClear();

      // Open level dropdown
      const levelSelect = screen.getByLabelText('Level');
      fireEvent.mouseDown(levelSelect);

      // Select 'Error'
      const errorOption = await screen.findByRole('option', { name: 'Error' });
      fireEvent.click(errorOption);

      await waitFor(() => {
        expect(mockFetchLogs).toHaveBeenCalledWith(100, 'error');
      });
    });

    test('changing line count triggers fetchLogs', async () => {
      render(<LogsPage />);
      mockFetchLogs.mockClear();

      // Open lines dropdown
      const linesSelect = screen.getByLabelText('Lines');
      fireEvent.mouseDown(linesSelect);

      // Select '500'
      const option500 = await screen.findByRole('option', { name: '500' });
      fireEvent.click(option500);

      await waitFor(() => {
        expect(mockFetchLogs).toHaveBeenCalledWith(500, 'all');
      });
    });

    test('search filters logs', () => {
      (useLogStore as unknown as jest.Mock).mockReturnValue({
        logs: ['INFO: Application started', 'ERROR: Connection failed', 'INFO: Request received'],
        loading: false,
        error: null,
        fetchLogs: mockFetchLogs,
      });
      render(<LogsPage />);

      const searchInput = screen.getByPlaceholderText('Search logs...');
      fireEvent.change(searchInput, { target: { value: 'error' } });

      expect(screen.getByText('ERROR: Connection failed')).toBeInTheDocument();
      expect(screen.queryByText('INFO: Application started')).not.toBeInTheDocument();
      expect(screen.queryByText('INFO: Request received')).not.toBeInTheDocument();
    });

    test('search is case insensitive', () => {
      (useLogStore as unknown as jest.Mock).mockReturnValue({
        logs: ['ERROR: Connection failed', 'error: lowercase error'],
        loading: false,
        error: null,
        fetchLogs: mockFetchLogs,
      });
      render(<LogsPage />);

      const searchInput = screen.getByPlaceholderText('Search logs...');
      fireEvent.change(searchInput, { target: { value: 'ERROR' } });

      expect(screen.getByText('ERROR: Connection failed')).toBeInTheDocument();
      expect(screen.getByText('error: lowercase error')).toBeInTheDocument();
    });
  });

  describe('Export Functionality', () => {
    test('export button creates and downloads file', () => {
      const mockLogs = ['Log 1', 'Log 2', 'Log 3'];
      (useLogStore as unknown as jest.Mock).mockReturnValue({
        logs: mockLogs,
        loading: false,
        error: null,
        fetchLogs: mockFetchLogs,
      });

      // Mock URL.createObjectURL and URL.revokeObjectURL
      const mockCreateObjectURL = jest.fn().mockReturnValue('blob:test-url');
      const mockRevokeObjectURL = jest.fn();
      global.URL.createObjectURL = mockCreateObjectURL;
      global.URL.revokeObjectURL = mockRevokeObjectURL;

      // Mock document.createElement to capture the anchor click
      const mockClick = jest.fn();
      const originalCreateElement = document.createElement.bind(document);
      jest.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
        const element = originalCreateElement(tagName);
        if (tagName === 'a') {
          element.click = mockClick;
        }
        return element;
      });

      render(<LogsPage />);
      const exportButton = screen.getByText('Export Logs');
      fireEvent.click(exportButton);

      expect(mockCreateObjectURL).toHaveBeenCalled();
      expect(mockClick).toHaveBeenCalled();
      expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:test-url');

      // Restore
      (document.createElement as jest.Mock).mockRestore();
    });

    test('export respects search filter', () => {
      const mockLogs = ['ERROR: Critical', 'INFO: Normal'];
      (useLogStore as unknown as jest.Mock).mockReturnValue({
        logs: mockLogs,
        loading: false,
        error: null,
        fetchLogs: mockFetchLogs,
      });

      // Mock Blob to capture content
      const mockBlob = jest.fn();
      global.Blob = mockBlob as any;
      global.URL.createObjectURL = jest.fn().mockReturnValue('blob:test');
      global.URL.revokeObjectURL = jest.fn();

      const mockClick = jest.fn();
      const originalCreateElement = document.createElement.bind(document);
      jest.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
        const element = originalCreateElement(tagName);
        if (tagName === 'a') {
          element.click = mockClick;
        }
        return element;
      });

      render(<LogsPage />);

      // Filter to only ERROR logs
      const searchInput = screen.getByPlaceholderText('Search logs...');
      fireEvent.change(searchInput, { target: { value: 'ERROR' } });

      // Export
      const exportButton = screen.getByText('Export Logs');
      fireEvent.click(exportButton);

      // Blob should be called with only filtered logs
      expect(mockBlob).toHaveBeenCalledWith(['ERROR: Critical'], { type: 'text/plain' });

      // Restore
      (document.createElement as jest.Mock).mockRestore();
    });
  });
});