import { render, screen, fireEvent } from '@testing-library/react';
import RiskEnginePage from './RiskEnginePage';
import useRiskStore from '../store/riskStore';

// Mock the store
jest.mock('../store/riskStore');

describe('RiskEnginePage', () => {
  const mockFetchStatus = jest.fn();
  const mockRunEvaluation = jest.fn();
  const mockBlockGroup = jest.fn();
  const mockUnblockGroup = jest.fn();
  const mockSkipGroup = jest.fn();

  const defaultStatus = {
    risk_engine_running: true,
    identified_loser: null,
    identified_winners: [],
    required_offset_usd: 0,
    config: {}
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: defaultStatus,
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
    });
  });

  test('renders loading state initially', () => {
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: null,
      loading: true,
      error: null,
      fetchStatus: mockFetchStatus,
    });
    render(<RiskEnginePage />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  test('renders error state', () => {
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: defaultStatus,
      loading: false,
      error: "Failed to fetch",
      fetchStatus: mockFetchStatus,
    });
    render(<RiskEnginePage />);
    expect(screen.getByText("Failed to fetch")).toBeInTheDocument();
  });

  test('renders empty state (no loser)', () => {
    render(<RiskEnginePage />);
    expect(screen.getByText("Risk Engine Panel")).toBeInTheDocument();
    expect(screen.getByText("Monitoring")).toBeInTheDocument();
    expect(screen.getByText(/No losing positions currently meet the criteria/i)).toBeInTheDocument();
  });

  test('renders identified loser and winners', () => {
    const statusWithLoser = {
      ...defaultStatus,
      identified_loser: {
        id: 'l1',
        symbol: 'BTCUSDT',
        unrealized_pnl_usd: -100,
        unrealized_pnl_percent: -5,
        risk_blocked: false,
        risk_skip_once: false
      },
      identified_winners: [
        { id: 'w1', symbol: 'ETHUSDT', unrealized_pnl_usd: 50 },
        { id: 'w2', symbol: 'SOLUSDT', unrealized_pnl_usd: 60 }
      ],
      required_offset_usd: 100
    };
    
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusWithLoser,
        loading: false,
        error: null,
        fetchStatus: mockFetchStatus,
        blockGroup: mockBlockGroup,
        skipGroup: mockSkipGroup,
        runEvaluation: mockRunEvaluation
      });

    render(<RiskEnginePage />);
    
    expect(screen.getByText(/Identified Loser:/i)).toBeInTheDocument();
    expect(screen.getByText(/BTCUSDT/i)).toBeInTheDocument();
    expect(screen.getByText(/ETHUSDT/i)).toBeInTheDocument();
    expect(screen.getByText(/SOLUSDT/i)).toBeInTheDocument();
    expect(screen.getByText(/\$100.00/i)).toBeInTheDocument(); // Required offset
  });

  test('calls runEvaluation when button clicked', () => {
    render(<RiskEnginePage />);
    const button = screen.getByText("Run Evaluation Now");
    fireEvent.click(button);
    expect(mockRunEvaluation).toHaveBeenCalled();
  });

  test('calls blockGroup when block button clicked', () => {
    const statusWithLoser = {
        ...defaultStatus,
        identified_loser: {
          id: 'l1',
          symbol: 'BTCUSDT',
          unrealized_pnl_usd: -100,
          unrealized_pnl_percent: -5,
          risk_blocked: false, // Unblocked, so Block button should show
          risk_skip_once: false
        }
    };
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusWithLoser,
        loading: false,
        fetchStatus: mockFetchStatus,
        blockGroup: mockBlockGroup,
        runEvaluation: mockRunEvaluation
    });

    render(<RiskEnginePage />);
    const button = screen.getByText("Block");
    fireEvent.click(button);
    expect(mockBlockGroup).toHaveBeenCalledWith('l1');
  });

  test('calls unblockGroup when unblock button clicked', () => {
    const statusWithLoser = {
        ...defaultStatus,
        identified_loser: {
          id: 'l1',
          symbol: 'BTCUSDT',
          unrealized_pnl_usd: -100,
          unrealized_pnl_percent: -5,
          risk_blocked: true, // Blocked, so Unblock button should show
          risk_skip_once: false
        }
    };
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusWithLoser,
        loading: false,
        fetchStatus: mockFetchStatus,
        unblockGroup: mockUnblockGroup,
        runEvaluation: mockRunEvaluation
    });

    render(<RiskEnginePage />);
    const button = screen.getByText("Unblock");
    fireEvent.click(button);
    expect(mockUnblockGroup).toHaveBeenCalledWith('l1');
  });

  test('calls skipGroup when skip button clicked', () => {
     const statusWithLoser = {
        ...defaultStatus,
        identified_loser: {
          id: 'l1',
          symbol: 'BTCUSDT',
          unrealized_pnl_usd: -100,
          unrealized_pnl_percent: -5,
          risk_blocked: false,
          risk_skip_once: false
        }
    };
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusWithLoser,
        loading: false,
        fetchStatus: mockFetchStatus,
        skipGroup: mockSkipGroup,
        runEvaluation: mockRunEvaluation
    });

    render(<RiskEnginePage />);
    const button = screen.getByText("Skip Once");
    fireEvent.click(button);
    expect(mockSkipGroup).toHaveBeenCalledWith('l1');
  });
});
