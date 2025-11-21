import useRiskStore from './riskStore';
import axios from 'axios';

jest.mock('axios');

describe('riskStore', () => {
  beforeEach(() => {
    useRiskStore.setState({
      status: null,
      loading: false,
      error: null,
    });
    jest.clearAllMocks();
  });

  it('fetchRiskStatus should call API and update state', async () => {
    const mockStatus = {
      identified_loser: null,
      identified_winners: [],
      required_offset_usd: 0,
      risk_engine_running: true,
      config: {},
    };
    (axios.get as jest.Mock).mockResolvedValue({ data: mockStatus });

    await useRiskStore.getState().fetchRiskStatus();

    expect(axios.get).toHaveBeenCalledWith('/api/v1/risk/status');
    expect(useRiskStore.getState().status).toEqual(mockStatus);
    expect(useRiskStore.getState().loading).toBe(false);
  });

  it('runRiskEvaluation should call API and refresh status', async () => {
    (axios.post as jest.Mock).mockResolvedValue({});
    (axios.get as jest.Mock).mockResolvedValue({ data: {} }); // Mock get for fetchRiskStatus
    const fetchSpy = jest.spyOn(useRiskStore.getState(), 'fetchRiskStatus');

    await useRiskStore.getState().runRiskEvaluation();

    expect(axios.post).toHaveBeenCalledWith('/api/v1/risk/run-evaluation');
    expect(fetchSpy).toHaveBeenCalled();
  });

  it('blockRiskForGroup should call API and refresh status', async () => {
    (axios.post as jest.Mock).mockResolvedValue({});
    (axios.get as jest.Mock).mockResolvedValue({ data: {} }); // Mock get for fetchRiskStatus
    const fetchSpy = jest.spyOn(useRiskStore.getState(), 'fetchRiskStatus');

    await useRiskStore.getState().blockRiskForGroup('123');

    expect(axios.post).toHaveBeenCalledWith('/api/v1/risk/123/block');
    expect(fetchSpy).toHaveBeenCalled();
  });
});
