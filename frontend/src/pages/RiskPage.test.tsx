import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RiskPage from './RiskPage';
import useRiskStore from '../store/riskStore';
import useConfirmStore from '../store/confirmStore';
import { act } from 'react-dom/test-utils';
import userEvent from '@testing-library/user-event';

// Mock Store
jest.mock('../store/riskStore');
jest.mock('../store/confirmStore', () => ({
    __esModule: true,
    default: {
        getState: jest.fn(),
    }
}));

const mockRiskStatus = {
  identified_loser: {
    id: 'loser1',
    symbol: 'BTCUSDT',
    unrealized_pnl_percent: -10,
    unrealized_pnl_usd: -100,
    risk_blocked: false,
    risk_skip_once: false,
    pyramids_reached: true,
    age_filter_passed: true,
    loss_threshold_reached: true,
    timer_expired: true,
  },
  identified_winners: [
    {
      id: 'winner1',
      symbol: 'ETHUSDT',
      unrealized_pnl_usd: 50,
    }
  ],
  required_offset_usd: 100,
  total_available_profit: 50,
  risk_engine_running: true,
  config: {
    max_open_positions_global: 5,
  },
  projected_plan: [],
};

describe('RiskPage', () => {
  const mockFetchStatus = jest.fn();
  const mockRunEvaluation = jest.fn();
  const mockBlockGroup = jest.fn();
  const mockUnblockGroup = jest.fn();
  const mockSkipGroup = jest.fn();
  const mockRequestConfirm = jest.fn();

  beforeEach(() => {
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: mockRiskStatus,
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
    });
    
    // Mock requestConfirm
    mockRequestConfirm.mockResolvedValue(true);
    (useConfirmStore.getState as jest.Mock).mockReturnValue({
        requestConfirm: mockRequestConfirm
    });
    
    jest.clearAllMocks();
  });

  test('renders risk status dashboard', async () => {
    await act(async () => {
        render(
        <MemoryRouter>
            <RiskPage />
        </MemoryRouter>
        );
    });

    expect(screen.getByText(/Risk Control Panel/i)).toBeInTheDocument();
    expect(screen.getByText(/Risk Engine Status/i)).toBeInTheDocument();
    
    // Check Status Display
    expect(screen.getByText(/max_open_positions_global/i)).toBeInTheDocument();
    
    // Check Loser Display
    expect(screen.getByText(/BTCUSDT/i)).toBeInTheDocument();
    expect(screen.getByText(/-100.00/i)).toBeInTheDocument();
    
    // Check Winner Display
    expect(screen.getByText(/ETHUSDT/i)).toBeInTheDocument();
    expect(screen.getByText(/50.00/i)).toBeInTheDocument();
  });

  test('triggers manual evaluation', async () => {
    await act(async () => {
        render(
        <MemoryRouter>
            <RiskPage />
        </MemoryRouter>
        );
    });

    const runButton = screen.getByRole('button', { name: /Run Risk Evaluation Now/i });
    await userEvent.click(runButton);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
        expect(mockRunEvaluation).toHaveBeenCalled();
    });
  });

  test('triggers block position', async () => {
    await act(async () => {
        render(
        <MemoryRouter>
            <RiskPage />
        </MemoryRouter>
        );
    });

    const blockButton = screen.getByRole('button', { name: /^Block$/i });
    await userEvent.click(blockButton);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
        expect(mockBlockGroup).toHaveBeenCalledWith('loser1');
    });
  });

  test('triggers skip next evaluation', async () => {
    await act(async () => {
        render(
        <MemoryRouter>
            <RiskPage />
        </MemoryRouter>
        );
    });

    const skipButton = screen.getByRole('button', { name: /Skip Next/i });
    await userEvent.click(skipButton);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
        expect(mockSkipGroup).toHaveBeenCalledWith('loser1');
    });
  });
});