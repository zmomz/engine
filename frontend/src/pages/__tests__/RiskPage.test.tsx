
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import RiskPage from '../RiskPage';
import useRiskStore from '../../store/riskStore';

// Mock the store
jest.mock('../../store/riskStore');

const mockUseRiskStore = useRiskStore as unknown as jest.Mock;

describe('RiskPage', () => {
  const mockRunEvaluation = jest.fn();
  const mockBlockGroup = jest.fn();
  const mockUnblockGroup = jest.fn();
  const mockSkipGroup = jest.fn();
  const mockFetchStatus = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockUseRiskStore.mockReturnValue({
      status: null,
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
    });
    
    // Mock window.confirm
    window.confirm = jest.fn(() => true);
  });

  it('renders loading state initially', () => {
     mockUseRiskStore.mockReturnValue({
      status: null,
      loading: true,
      error: null,
      fetchStatus: mockFetchStatus,
    });
    
    render(<RiskPage />);
    expect(screen.getByText(/Loading risk status.../i)).toBeInTheDocument();
  });

  it('renders error state', () => {
     mockUseRiskStore.mockReturnValue({
      status: null,
      loading: false,
      error: "Failed to fetch",
      fetchStatus: mockFetchStatus,
    });
    
    render(<RiskPage />);
    expect(screen.getByText(/Error: Failed to fetch/i)).toBeInTheDocument();
  });

  it('renders status when loaded', () => {
    const mockStatus = {
      risk_engine_running: true,
      config: { max_daily_loss_usd: 100 },
      identified_loser: null,
      identified_winners: [],
      required_offset_usd: 0,
    };
    
    mockUseRiskStore.mockReturnValue({
      status: mockStatus,
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
    });

    render(<RiskPage />);
    
    expect(screen.getByText(/Risk Engine Status/i)).toBeInTheDocument();
    expect(screen.getByText(/max_daily_loss_usd/i)).toBeInTheDocument();
    expect(screen.getByText(/100/i)).toBeInTheDocument();
  });

  it('renders identified loser and actions', () => {
    const mockStatus = {
      risk_engine_running: true,
      config: {},
      identified_loser: {
        id: 'loser-1',
        symbol: 'BTC/USD',
        unrealized_pnl_percent: -10,
        unrealized_pnl_usd: -50,
        risk_blocked: false,
        risk_skip_once: false,
      },
      identified_winners: [],
      required_offset_usd: 50,
    };

    mockUseRiskStore.mockReturnValue({
      status: mockStatus,
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      blockGroup: mockBlockGroup,
      skipGroup: mockSkipGroup,
    });

    render(<RiskPage />);

    expect(screen.getByText(/BTC\/USD/i)).toBeInTheDocument();
    
    // Test Block Action
    const blockButton = screen.getByText('Block');
    fireEvent.click(blockButton);
    expect(window.confirm).toHaveBeenCalled();
    expect(mockBlockGroup).toHaveBeenCalledWith('loser-1');

    // Test Skip Action
    const skipButton = screen.getByText('Skip Next');
    fireEvent.click(skipButton);
    expect(mockSkipGroup).toHaveBeenCalledWith('loser-1');
  });

  it('renders unblock button when blocked', () => {
    const mockStatus = {
        risk_engine_running: true,
        config: {},
        identified_loser: {
          id: 'loser-1',
          symbol: 'BTC/USD',
          unrealized_pnl_percent: -10,
          unrealized_pnl_usd: -50,
          risk_blocked: true, // Blocked
          risk_skip_once: false,
        },
        identified_winners: [],
        required_offset_usd: 50,
      };
  
      mockUseRiskStore.mockReturnValue({
        status: mockStatus,
        loading: false,
        error: null,
        fetchStatus: mockFetchStatus,
        unblockGroup: mockUnblockGroup,
      });
  
      render(<RiskPage />);
      
      const unblockButton = screen.getByText('Unblock');
      fireEvent.click(unblockButton);
      expect(mockUnblockGroup).toHaveBeenCalledWith('loser-1');
  });

  it('calls runEvaluation on button click', () => {
     const mockStatus = {
      risk_engine_running: true,
      config: {},
      identified_loser: null,
      identified_winners: [],
      required_offset_usd: 0,
    };
    
    mockUseRiskStore.mockReturnValue({
      status: mockStatus,
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
    });

    render(<RiskPage />);
    
    const runButton = screen.getByText('Run Risk Evaluation Now');
    fireEvent.click(runButton);
    expect(window.confirm).toHaveBeenCalled();
    expect(mockRunEvaluation).toHaveBeenCalled();
  });
});
